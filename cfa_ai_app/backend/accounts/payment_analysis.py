from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models, transaction
from django.db.models import Avg, F, Q, ExpressionWrapper, DurationField, Sum
from django.utils import timezone
from transactions.models import (
    TallyTransaction, BankBalance, PaymentPattern, TransactionMatching, PartyBalance,
    FixedExpense
)
from .models import LedgerOpeningBalance
import numpy as np
import logging

logger = logging.getLogger(__name__)
import pandas as pd
import json
from django.db import transaction
from collections import defaultdict
import logging
logger = logging.getLogger(__name__)

class PaymentPatternAnalyzer:
    def get_bank_balance(self):
        try:
            bank_balance = BankBalance.objects.filter(
                company_id=self.company_id
            ).order_by('-updated_at').first()
            if bank_balance:
                initial_balance = float(bank_balance.balance)
                logger.info(f"Using bank balance: {initial_balance} from {bank_balance.updated_at}")
            else:
                # Calculate from transactions if no bank balance
                transactions = TallyTransaction.objects.filter(company_id=self.company_id)
                total_receipts = transactions.filter(
                    register_type='receipt'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                total_payments = transactions.filter(
                    register_type='payment'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                initial_balance = float(total_receipts - total_payments)
                logger.warning(f"No bank balance found, calculated from transactions: {initial_balance}")
                
                # Create bank balance record
                BankBalance.objects.create(
                    company_id=self.company_id,
                    balance=initial_balance,
                    account_name='default'
                )
            return initial_balance
        except Exception as e:
            logger.error(f"Error getting bank balance: {str(e)}")
            return 0
    def __init__(self, company_id, since_date=None, transaction_ids=None):
        if not company_id:
            raise ValueError("Company ID is required")
            
        self.company_id = company_id
        # Optional scoping parameters: restrict analysis to transactions on/after since_date
        # or to a list of transaction IDs. These are optional and existing callers are
        # backward-compatible when they are not provided.
        self.since_date = since_date
        self.transaction_ids = transaction_ids
        self.payment_patterns = {}
        self.fixed_expenses = {}
        self.unpaid_sales = []

        logger.info(f"Initializing PaymentPatternAnalyzer for company {company_id}")

        # Validate company existence and data
        try:
            # Check if we have any transactions first
            transaction_count = TallyTransaction.objects.filter(company_id=self.company_id).count()
            sales_count = TallyTransaction.objects.filter(company_id=self.company_id, register_type='sales').count()
            receipt_count = TallyTransaction.objects.filter(company_id=self.company_id, register_type='receipt').count()

            logger.info(f"Data validation - Total: {transaction_count}, Sales: {sales_count}, Receipts: {receipt_count}")
            logger.info(f"Found {transaction_count} total transactions: {sales_count} sales and {receipt_count} receipts")
        except Exception as e:
            logger.error(f"Error validating transaction data: {str(e)}")
            raise ValueError("Error validating transaction data")

        if transaction_count == 0:
            logger.error(f"No transactions found for company {company_id}")
            raise ValueError("No transaction data found. Please import your Tally data first using the desktop sync agent or manual import.")

        try:
            # Initialize party balances and patterns on creation
            self._ensure_party_balances()
        except Exception as e:
            logger.error(f"Error initializing party balances for company {company_id}: {str(e)}")
            raise ValueError(f"Error initializing payment analysis: {str(e)}")
        
    def _ensure_party_balances(self):
        """Ensure party balances exist"""
        try:
            # Check if we have any party balances
            balance_count = PartyBalance.objects.filter(company_id=self.company_id).count()
            logger.info(f"Found {balance_count} existing party balances for company {self.company_id}")
            
            if balance_count == 0:
                logger.info(f"No party balances found for company {self.company_id}. Generating...")
                balances_generated = self._generate_party_balances()
                logger.info(f"Generated {balances_generated} party balances")
                
        except Exception as e:
            logger.error(f"Error ensuring party balances: {str(e)}")
            raise
            
    def _generate_party_balances(self):
        """Generate party balances from opening balances and transactions"""
        try:
            with transaction.atomic():
                # Get all parties from both opening balances and transactions
                parties = set(list(self._base_transactions().values_list('party_name', flat=True).distinct()) + 
                list(LedgerOpeningBalance.objects.filter(
                    company_id=self.company_id
                ).values_list('ledger_name', flat=True).distinct()))
                
                if not parties:
                    logger.warning(f"No parties found for company {self.company_id}")
                    return 0
                
                balances_created = 0
                
                for party_name in parties:
                    try:
                        # Get opening balance if exists
                        opening_balance = LedgerOpeningBalance.objects.filter(
                            company_id=self.company_id,
                            ledger_name=party_name
                        ).values('opening_balance').first()
                        
                        initial_balance = Decimal(str(opening_balance['opening_balance'])) if opening_balance else Decimal('0.00')
                        
                        # Calculate transactions
                        sales = TallyTransaction.objects.filter(
                            company_id=self.company_id,
                            party_name=party_name,
                            register_type='sales'
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                        
                        receipts = TallyTransaction.objects.filter(
                            company_id=self.company_id,
                            party_name=party_name,
                            register_type='receipt'
                        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                        
                        # Calculate running balance
                        # Opening balance + Sales - Receipts = Current Balance
                        # We store current_balance as negative when the party owes us money
                        raw_balance = initial_balance + sales - receipts
                        # If raw_balance is positive it means party has net receivable -> we store negative
                        current_balance = -raw_balance if raw_balance > 0 else raw_balance
                        
                        latest_txn = TallyTransaction.objects.filter(
                            company_id=self.company_id,
                            party_name=party_name
                        ).order_by('-date').values('date').first()
                        
                        # Create or update party balance
                        PartyBalance.objects.update_or_create(
                            company_id=self.company_id,
                            party_name=party_name,
                            defaults={
                                'current_balance': current_balance,
                                'expected_payment_date': latest_txn['date'] if latest_txn else timezone.now().date(),
                                'last_updated': timezone.now()
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error calculating balance for {party_name}: {str(e)}")
                        balances_created += 1
                        continue
                    except Exception as e:
                        logger.error(f"Error processing party {party_name}: {str(e)}")
                        continue
                
                logger.info(f"Generated party balances for {len(parties)} parties")
                
        except Exception as e:
            logger.error(f"Error generating party balances: {str(e)}")
            raise
        
    def _update_transaction_matching(self, sale, receipt, allocated_amount):
        """Create or update transaction matching records"""
        try:
            with transaction.atomic():
                # Check if matching already exists
                existing_match = TransactionMatching.objects.filter(
                    source_transaction=sale,
                    target_transaction=receipt
                ).first()
                
                if existing_match:
                    # Update existing match if found
                    existing_match.matched_amount = allocated_amount
                    existing_match.save()
                else:
                    # Create new match if not found
                    delay_days = (receipt.date - sale.date).days
                    TransactionMatching.objects.create(
                        source_transaction=sale,
                        target_transaction=receipt,
                        matched_amount=allocated_amount,
                        delay_days=delay_days
                    )
                
                # Update remaining amounts for both transactions
                sale.remaining_amount = (sale.remaining_amount or sale.amount) - allocated_amount
                receipt.remaining_amount = (receipt.remaining_amount or receipt.amount) - allocated_amount
                
                sale.save()
                receipt.save()
                
        except Exception as e:
            logger.error(f"Error updating transaction matching: {str(e)}")
            raise
                
        except Exception as e:
            logger.error(f"Error updating transaction matching: {str(e)}")
            raise
            
    def _save_payment_pattern(self, party_name, pattern_data):
        """Save or update payment pattern in database with validation"""
        try:
            if not self.company_id:
                raise ValueError("company_id is not set")
            
            if not party_name:
                raise ValueError("party_name is required")
                
            # Validate pattern data
            avg_payment_days = pattern_data.get('avg_payment_days')
            if avg_payment_days is None or avg_payment_days < 0:
                logger.warning(f"Invalid avg_payment_days for {party_name}: {avg_payment_days}, using default")
                avg_payment_days = 30  # Default to 30 days
                
            confidence_score = pattern_data.get('confidence_score', 0)
            if confidence_score < 0 or confidence_score > 1:
                logger.warning(f"Invalid confidence_score for {party_name}: {confidence_score}, normalizing")
                confidence_score = max(0, min(confidence_score, 1))  # Clamp between 0 and 1
                
            defaults = {
                'avg_payment_days': avg_payment_days,
                'confidence_score': confidence_score,
                'delay_std_deviation': pattern_data.get('std_deviation', 0),
                'pattern_consistency': confidence_score,
                'sample_size': pattern_data.get('sample_size', 0),
                'last_analysis_date': timezone.now().date(),
                'data_quality': 'good' if confidence_score > 0.7 else 'fair' if confidence_score > 0.4 else 'poor'
            }
            
            PaymentPattern.objects.update_or_create(
                company_id=self.company_id,
                party_name=party_name,
                defaults=defaults
            )
        except Exception as e:
            print(f"Error in _save_payment_pattern: {str(e)}")
            raise

    def get_unpaid_amounts(self):
        """Get all unpaid amounts from party balances"""
        try:
            unpaid = []
            party_balances = PartyBalance.objects.filter(company_id=self.company_id)
            
            for balance in party_balances:
                if balance.current_balance != 0:
                    unpaid.append({
                        'party_name': balance.party_name,
                        'amount': float(balance.current_balance),
                        'last_updated': balance.last_updated,
                        'expected_payment_date': balance.expected_payment_date
                    })
            
            return unpaid
        except Exception as e:
            logger.error(f"Error getting unpaid amounts: {str(e)}")
            raise

    def get_fixed_expenses(self):
        """Get all fixed expenses"""
        return FixedExpense.objects.filter(company_id=self.company_id)

    def _base_transactions(self):
        """Return a base queryset for company transactions optionally scoped by since_date or ids."""
        qs = TallyTransaction.objects.filter(company_id=self.company_id)
        if getattr(self, 'since_date', None):
            qs = qs.filter(date__gte=self.since_date)
        if getattr(self, 'transaction_ids', None):
            qs = qs.filter(id__in=self.transaction_ids)
        return qs

    def analyze_payment_patterns(self):
        """Analyze payment patterns and generate sophisticated payment predictions"""
        try:
            current_date = timezone.now().date()
            unpaid_amounts = self.get_unpaid_amounts()
            fixed_expenses = self.get_fixed_expenses()
            
            predictions = []
            total_patterns = 0
            total_predictions = 0
            
            # Get company's cash position
            bank_balance = self.get_bank_balance()
            logger.info(f"Starting analysis with bank balance: {bank_balance}")
            logger.info(f"Analyzing patterns for {len(unpaid_amounts)} unpaid amounts")
            
            # Analyze party payment history and patterns
            party_histories = {}
            for unpaid in unpaid_amounts:
                party_name = unpaid['party_name']
                if party_name not in party_histories:
                    # Get full payment history
                    history = self._base_transactions().filter(
                        party_name=party_name,
                        register_type__in=['receipt', 'payment']
                    ).order_by('date')
                    
                    # Get sales history
                    sales_history = self._base_transactions().filter(
                        party_name=party_name,
                        register_type='sales'
                    ).order_by('date')
                    
                    party_histories[party_name] = {
                        'payments': list(history),
                        'sales': list(sales_history)
                    }
            
            # Sort by priority score (combination of amount size and payment reliability)
            scored_unpaid = []
            for unpaid in unpaid_amounts:
                party_name = unpaid['party_name']
                amount = float(unpaid['amount'])
                history = party_histories[party_name]
                
                # Calculate payment reliability score
                total_payments = sum(1 for p in history['payments'] if p.amount > 0)
                total_sales = len(history['sales'])
                reliability = total_payments / max(total_sales, 1) if total_sales > 0 else 0.5
                
                # Calculate average payment amount
                avg_payment = (sum(float(p.amount) for p in history['payments'] if p.amount > 0) 
                             / max(total_payments, 1) if total_payments > 0 else abs(amount))
                
                # Priority score combines amount size, reliability and payment history
                priority_score = (abs(amount) * reliability * (avg_payment / max(abs(amount), 1)))
                
                scored_unpaid.append({
                    **unpaid,
                    'priority_score': priority_score,
                    'reliability': reliability
                })
            
            # Sort by priority score
            scored_unpaid.sort(key=lambda x: x['priority_score'], reverse=True)
            
            # Process each unpaid amount with sophisticated prediction
            for unpaid in scored_unpaid:
                party_name = unpaid['party_name']
                amount = unpaid['amount']
                reliability = unpaid['reliability']
                
                try:
                    pattern = PaymentPattern.objects.filter(
                        company_id=self.company_id,
                        party_name=party_name
                    ).first()
                    
                    if pattern:
                        total_patterns += 1
                        history = party_histories.get(party_name, {
                            'payments': [],
                            'sales': []
                        })
                except Exception as e:
                    logger.error(f"Error getting payment pattern for {party_name}: {str(e)}")
                    continue
                    
                if pattern:  # Only continue if we successfully got the pattern
                    logger.info(f"Analyzing pattern for {party_name}: "
                              f"Amount={amount}, "
                              f"Payment History={len(history['payments'])}, "
                              f"Sales History={len(history['sales'])}")
                    
                    # Analyze seasonal patterns
                    month_stats = defaultdict(list)
                    for payment in history['payments']:
                        month_stats[payment.date.month].append(float(payment.amount))
                    
                    # Calculate month-specific delay
                    current_month = current_date.month
                    month_avg_delay = pattern.avg_payment_days
                    if month_stats[current_month]:
                        month_delays = [p.date.day for p in history['payments'] 
                                      if p.date.month == current_month]
                        if month_delays:
                            month_avg_delay = sum(month_delays) / len(month_delays)
                    
                    # Calculate expected date with seasonal adjustment
                    base_delay = pattern.avg_payment_days or 30
                    seasonal_factor = 1.0
                    if month_stats[current_month]:
                        seasonal_factor = (sum(month_stats[current_month]) / len(month_stats[current_month])) / \
                                       (sum(sum(v) / len(v) for v in month_stats.values()) / len(month_stats))
                    
                    adjusted_delay = base_delay * seasonal_factor
                    expected_date = current_date + timedelta(days=int(adjusted_delay))
                    
                    # Simplified prediction without complex confidence calculations
                    predictions.append({
                        'party_name': party_name,
                        'amount': amount,
                        'expected_date': expected_date,
                        'confidence_score': 1.0,  # Set to 1.0 as we're focusing on amounts
                        'type': 'receivable' if amount > 0 else 'payable',
                        'reliability': round(reliability, 2),
                        'seasonal_factor': round(seasonal_factor, 2),
                        'payment_history_count': len(history['payments'])
                    })
                    total_predictions += 1
            
            # Log prediction summary before processing fixed expenses
            logger.info(f"Generated {len(predictions)} predictions from {total_patterns} patterns")
            
            # Add fixed expenses to predictions - simplified version
            for expense in fixed_expenses:
                try:
                    if hasattr(expense, 'next_due_date') and expense.next_due_date and expense.amount:
                        logger.info(f"Adding fixed expense: {expense.description} - Amount: {expense.amount}")
                        predictions.append({
                            'party_name': getattr(expense, 'description', 'Fixed Expense'),
                            'amount': -float(expense.amount),  # Negative for outflow
                            'expected_date': expense.next_due_date,
                            'confidence_score': 1.0,  # All predictions treated equally
                            'type': 'fixed_expense',
                            'reliability': 1.0,
                            'recurring': True
                        })
                        total_predictions += 1
                except Exception as e:
                    logger.error(f"Error processing fixed expense: {str(e)}")
                    continue

            # Group and analyze predictions by date
            daily_predictions = defaultdict(lambda: {
                'inflow': 0, 
                'outflow': 0,
                'fixed_expenses': 0,
                'high_confidence_inflow': 0,
                'high_confidence_outflow': 0,
                'transactions': []
            })

            running_balance = float(bank_balance)
            
            # Sort all predictions by date first
            predictions.sort(key=lambda x: x['expected_date'])
            
            for pred in predictions:
                date_key = pred['expected_date'].strftime('%Y-%m-%d')
                amount = float(pred['amount'])
                
                if amount > 0:  # Inflow
                    daily_predictions[date_key]['inflow'] += amount
                    daily_predictions[date_key]['high_confidence_inflow'] += amount  # All inflows treated as high confidence
                else:  # Outflow
                    amount_abs = abs(amount)
                    daily_predictions[date_key]['outflow'] += amount_abs
                    if pred.get('type') == 'fixed_expense':
                        daily_predictions[date_key]['fixed_expenses'] += amount_abs
                    daily_predictions[date_key]['high_confidence_outflow'] += amount_abs  # All outflows treated as high confidence
                
                # Track individual transactions for detailed view - simplified
                transaction_detail = {
                    'party_name': pred['party_name'],
                    'amount': amount,
                    'type': pred.get('type', 'unknown')
                }
                
                # Log significant transactions (high value only)
                if abs(amount) > 100000:
                    logger.info(f"Significant prediction: {transaction_detail}")
                    
                daily_predictions[date_key]['transactions'].append(transaction_detail)

            # Convert to sorted list with running balances
            sorted_predictions = []
            for date_key in sorted(daily_predictions.keys()):
                day_data = daily_predictions[date_key]
                
                # Calculate net flow and update running balance
                net_flow = day_data['inflow'] - day_data['outflow']
                running_balance += net_flow
                
                sorted_predictions.append({
                    'date': date_key,
                    'inflow': round(day_data['inflow'], 2),
                    'outflow': round(day_data['outflow'], 2),
                    'fixed_expenses': round(day_data['fixed_expenses'], 2),
                    'net': round(net_flow, 2),
                    'running_balance': round(running_balance, 2),
                    'transactions': sorted(day_data['transactions'], 
                                        key=lambda x: -abs(x['amount'])),  # Sort only by amount
                    'transaction_count': len(day_data['transactions'])
                })

            return {
                'predictions': sorted_predictions,
                'total_patterns': total_patterns,
                'total_predictions': total_predictions
            }
        except Exception as e:
            logger.error(f"Error analyzing payment patterns: {str(e)}")
            raise

    def detect_unpaid_sales(self):
        """Detect sales that have not been fully paid"""
        try:
            if not self.company_id:
                return []
            
            # Get all sales transactions
            sales = self._base_transactions().filter(
                register_type='sales'
            ).order_by('date')
            
            unpaid_sales = []
            
            for sale in sales:
                # Calculate remaining amount
                remaining_amount = sale.remaining_amount or sale.amount
                
                # If there's still remaining amount, it's unpaid
                if remaining_amount > Decimal('0'):
                    unpaid_sales.append({
                        'id': sale.id,
                        'date': sale.date,
                        'amount': float(sale.amount),
                        'remaining_amount': float(remaining_amount),
                        'party_name': sale.party_name,
                        'voucher_number': sale.voucher_number
                    })
            
            self.unpaid_sales = unpaid_sales
            return unpaid_sales
            
        except Exception as e:
            print(f"Error detecting unpaid sales: {str(e)}")
            return []

    def predict_payment_dates(self):
        """Predict payment dates for unpaid sales based on party payment patterns"""
        try:
            if not self.unpaid_sales:
                self.detect_unpaid_sales()
            
            # Load patterns from database if not loaded
            if not self.payment_patterns:
                saved_patterns = PaymentPattern.objects.filter(company_id=self.company_id)
                for pattern in saved_patterns:
                    self.payment_patterns[pattern.party_name] = {
                        'avg_payment_days': pattern.avg_payment_days,
                        'confidence': pattern.confidence_score,
                        'sample_size': pattern.sample_size,
                        'std_deviation': pattern.delay_std_deviation
                    }
            
            predictions = []
            current_date = timezone.now().date()
            
            for sale in self.unpaid_sales:
                party_name = sale['party_name']
                pattern = None
                
                # First try to get saved pattern
                if party_name in self.payment_patterns:
                    pattern = self.payment_patterns[party_name]
                else:
                    # If no pattern exists, try to analyze new one
                    print(f"No saved pattern found for {party_name}, analyzing transactions...")
                    self.analyze_payment_patterns()
                    if party_name in self.payment_patterns:
                        pattern = self.payment_patterns[party_name]
                
                if pattern:
                    sale_date = sale['date']
                    if isinstance(sale_date, str):
                        sale_date = datetime.strptime(sale_date, '%Y-%m-%d').date()
                    predicted_date = sale_date + timedelta(days=pattern['avg_payment_days'])
                    # Log prediction attempt
                    print(f"Predicting payment for sale {sale['id']} (party: {party_name}) on {predicted_date}, remaining: {sale['remaining_amount']}, confidence: {pattern['confidence']}")
                    # Always include predictions, add overdue flag
                    predictions.append({
                        'party_name': party_name,
                        'date': predicted_date.strftime('%Y-%m-%d'),
                        'amount': round(float(sale['remaining_amount']), 2),
                        'confidence': pattern['confidence'],
                        'sale_reference': sale.get('voucher_number', ''),
                        'remaining_amount': round(float(sale['remaining_amount']), 2),
                        'predicted_payment_date': predicted_date.strftime('%Y-%m-%d'),
                        'confidence': round(float(pattern['confidence']), 2),
                        'avg_delay_days': int(pattern['avg_payment_days']),
                        'voucher_number': sale['voucher_number'],
                        'is_overdue': predicted_date < current_date
                    })
            
            return predictions
            
        except Exception as e:
            print(f"Error predicting payment dates: {str(e)}")
            return []

    def calculate_party_balances(self):
        """Calculate current balances for each party"""
        try:
            if not self.company_id:
                return {}
            
            # Get opening balances
            opening_balances = {}
            try:
                from accounts.models import LedgerOpeningBalance
                balances = LedgerOpeningBalance.objects.filter(company_id=self.company_id)
                for balance in balances:
                    opening_balances[balance.ledger_name] = Decimal(str(balance.opening_balance))
            except Exception as e:
                logger.error(f"Error getting opening balances: {str(e)}")
            
            # Get all transactions for the company, excluding bank accounts
            transactions = self._base_transactions().exclude(
                party_name__icontains='bank'
            ).order_by('date')
            
            party_balances = defaultdict(Decimal)
            
            # Initialize with opening balances
            for party_name, balance in opening_balances.items():
                if not 'bank' in party_name.lower():  # Exclude bank accounts
                    party_balances[party_name] = balance
            
            # Calculate running balances
            for transaction in transactions:
                party_name = transaction.party_name
                amount = Decimal(str(transaction.amount))  # Ensure Decimal
                
                if transaction.register_type == 'sales':
                    # Sales increase receivable (negative means they owe us)
                    party_balances[party_name] -= amount
                elif transaction.register_type == 'receipt':
                    # Receipts decrease receivable
                    party_balances[party_name] += amount
                elif transaction.register_type == 'payment':
                    # We ignore payments as they're not relevant for receivables
                    continue
            
            # Convert to list format and filter negative balances (unpaid amounts)
            unpaid_balances = []
            for party_name, balance in party_balances.items():
                if balance < Decimal('0'):  # Negative balance means we're owed money
                    unpaid_balances.append({
                        'party_name': party_name,
                        'current_balance': float(abs(balance)),
                        'expected_payment_date': None,  # Will be calculated based on patterns
                        'payment_probability': 0.5  # Default probability
                    })
            
            return unpaid_balances
            
        except Exception as e:
            print(f"Error calculating party balances: {str(e)}")
            return {}

    def analyze_fixed_expenses(self):
        """Identify and analyze fixed/recurring expenses"""
        try:
            expenses = TallyTransaction.objects.filter(
                company_id=self.company_id,
                register_type='payment'
            ).order_by('date')

            expenses_values = expenses.values()
            
            if not expenses_values:
                logger.info("No expenses found for fixed expense analysis")
                return {}  # Return empty if no expenses
        except Exception as e:
            logger.error(f"Error querying expenses: {str(e)}")
            return {}

        expenses_df = pd.DataFrame(expenses_values)
        
        if 'party_name' not in expenses_df.columns or 'date' not in expenses_df.columns:
            return self.fixed_expenses  # Return empty if required columns missing
            
        for party_name in expenses_df['party_name'].unique():
            party_expenses = expenses_df[expenses_df['party_name'] == party_name]
            
            # Check for regular intervals and consistent amounts
            amounts = [float(amt) for amt in party_expenses['amount']]
            dates = [date if isinstance(date, datetime) else timezone.make_aware(datetime.combine(date, datetime.min.time()))
                    for date in party_expenses['date']]
            dates.sort()  # Ensure dates are in order
            
            if len(dates) >= 3:  # Need at least 3 transactions to identify pattern
                try:
                    # Calculate intervals between payments
                    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                    avg_interval = float(np.mean(intervals))
                    std_interval = float(np.std(intervals)) if len(intervals) > 1 else 0
                    
                    # Calculate amount consistency
                    avg_amount = float(np.mean(amounts))
                    std_amount = float(np.std(amounts)) if len(amounts) > 1 else 0
                    
                    # If intervals and amounts are consistent (low std dev)
                    if std_interval < avg_interval * 0.2 and std_amount < avg_amount * 0.1:
                        # This appears to be a fixed expense
                        self.fixed_expenses[party_name] = {
                            'amount': round(avg_amount, 2),
                            'interval_days': round(avg_interval),
                            'confidence': min(len(dates) / 12, 1.0),  # More history = higher confidence
                            'last_payment_date': dates[-1].date().strftime('%Y-%m-%d')
                        }
                except Exception as e:
                    print(f"Error analyzing fixed expenses for {party_name}: {str(e)}")
                    continue

        return self.fixed_expenses

    def predict_future_payments(self, days=90):
        """Predict future payments and receipts"""
        try:
            # First check if we have transaction data
            transactions = TallyTransaction.objects.filter(company_id=self.company_id)
            if not transactions.exists():
                logger.error(f"No transactions found for company {self.company_id}")
                raise ValueError("No transaction data found. Please import your Tally data first using the desktop sync agent or manual import.")
                
            # Check if we have the minimum required transaction types
            sales = transactions.filter(register_type='sales').exists()
            receipts = transactions.filter(register_type='receipt').exists()
            
            if not sales or not receipts:
                logger.error(f"Missing transaction types for company {self.company_id}. Sales: {sales}, Receipts: {receipts}")
                raise ValueError("Missing required transaction types. Need both sales and receipt transactions.")
            
            # Ensure we have both party balances and payment patterns
            self._ensure_party_balances()
            if not self.payment_patterns:
                logger.info("No payment patterns found, analyzing patterns first")
                self.analyze_payment_patterns()
            
            # Initialize variables
            current_date = timezone.now().date()
            end_date = current_date + timedelta(days=days)
            
            # Get initial bank balance and validate
            try:
                bank_balance = BankBalance.objects.filter(
                    company_id=self.company_id
                ).order_by('-updated_at').first()
                
                if bank_balance:
                    initial_balance = float(bank_balance.balance)
                    logger.info(f"Using bank balance: {initial_balance} from {bank_balance.updated_at}")
                else:
                    # Calculate from transactions if no bank balance
                    total_receipts = transactions.filter(
                        register_type='receipt'
                    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    
                    total_payments = transactions.filter(
                        register_type='sales'
                    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    
                    initial_balance = float(total_receipts - total_payments)
                    logger.warning(f"No bank balance found, calculated from transactions: {initial_balance}")
                    
                    # Create bank balance record
                    BankBalance.objects.create(
                        company_id=self.company_id,
                        balance=initial_balance,
                        account_name='default'
                    )
            except Exception as e:
                logger.error(f"Error getting bank balance: {str(e)}")
                initial_balance = 0
            logger.info(f"Starting predictions with initial balance: {initial_balance}, data range: {current_date} to {end_date}")
            
            # Load saved patterns if not already loaded
            if not self.payment_patterns:
                try:
                    saved_patterns = PaymentPattern.objects.filter(company_id=self.company_id)
                    for pattern in saved_patterns:
                        key = pattern.party_name.lower().strip() if pattern.party_name else pattern.party_name
                        self.payment_patterns[key] = {
                            'avg_delay': int(pattern.avg_payment_days or 30),
                            'avg_payment_days': int(pattern.avg_payment_days or 30),
                            'confidence': float(pattern.confidence_score or 0.5),
                            'sample_size': int(pattern.sample_size or 0),
                            'std_deviation': float(pattern.delay_std_deviation or 0)
                        }
                    logger.info(f"Loaded {len(saved_patterns)} existing payment patterns")
                except Exception as e:
                    logger.error(f"Error loading payment patterns: {str(e)}")
                    self.payment_patterns = {}
            
            # Load saved patterns if not already loaded
            if not self.payment_patterns:
                try:
                    saved_patterns = PaymentPattern.objects.filter(company_id=self.company_id)
                    if not saved_patterns.exists():
                        # No patterns found, analyze patterns first
                        self.analyze_payment_patterns()
                        saved_patterns = PaymentPattern.objects.filter(company_id=self.company_id)
                    
                    for pattern in saved_patterns:
                        try:
                            key = pattern.party_name.lower().strip() if pattern.party_name else pattern.party_name
                            self.payment_patterns[key] = {
                                'avg_delay': int(pattern.avg_payment_days or 30),
                                'avg_payment_days': int(pattern.avg_payment_days or 30),
                                'confidence': float(pattern.confidence_score or 0.5),
                                'sample_size': int(pattern.sample_size or 1),
                                'std_deviation': float(pattern.delay_std_deviation or 0)
                            }
                        except (AttributeError, ValueError, TypeError) as e:
                            logger.error(f"Error loading pattern for {pattern.party_name}: {str(e)}")
                            continue
                            
                    if not self.payment_patterns:
                        logger.warning("No valid payment patterns found, adding fallback")
                        self.payment_patterns['Default'] = {
                            'avg_delay': 30,
                            'confidence': 0.5,
                            'sample_size': 1,
                            'std_deviation': 0
                        }
                except Exception as e:
                    logger.error(f"Error loading payment patterns: {str(e)}")
                    # Add fallback pattern
                    self.payment_patterns['Default'] = {
                        'avg_delay': 30,
                        'confidence': 0.5,
                        'sample_size': 1,
                        'std_deviation': 0
                    }
        
            # Load saved fixed expenses if not already loaded
            if not self.fixed_expenses:
                fixed_expenses = FixedExpense.objects.filter(company_id=self.company_id)
                for expense in fixed_expenses:
                    # Get latest payment from transactions for this description
                    try:
                        last_payment = TallyTransaction.objects.filter(
                            company_id=self.company_id,
                            description__icontains=expense.description,
                            register_type='payment'
                        ).order_by('-date').first()
                        
                        last_date = last_payment.date if last_payment else current_date
                    except Exception:
                        last_date = current_date
                    finally:
                        self.fixed_expenses[expense.description] = {
                            'amount': float(expense.amount),
                            'interval_days': int(expense.interval_days),
                            'confidence': float(expense.pattern_consistency),
                            'last_payment_date': last_date.strftime('%Y-%m-%d')
                        }
        
            print(f"Loaded {len(self.payment_patterns)} payment patterns and {len(self.fixed_expenses)} fixed expenses")
        
            # Get party balances and their latest sales
            try:
                # Get all parties with negative balances (they owe us money)
                # Get all parties with negative balances (they owe us money)
                party_balances = PartyBalance.objects.filter(
                    company_id=self.company_id,
                    current_balance__lt=0
                ).select_related()

                if not party_balances.exists():
                    logger.info("No parties with unpaid balances found")
                    return {
                        'data': {
                            'company_id': str(self.company_id),
                            'predictions': [],
                            'initial_balance': round(float(initial_balance), 2),
                            'lastUpdated': timezone.now().isoformat(),
                            'dataPoints': {'totalPredictions': 0, 'totalParties': 0, 'fixedExpenses': 0},
                            'insights': {'total_expected_receipts': 0, 'total_expected_expenses': 0, 'net_cashflow': 0}
                        },
                        'status': 'success'
                    }

                predictions = []
                for balance in party_balances:
                    # Normalize party name for lookup
                    party_key = balance.party_name.lower().strip() if balance.party_name else balance.party_name
                    # Get pattern for this party using normalized key
                    pattern = self.payment_patterns.get(party_key)
                    if not pattern:
                        # Try case-insensitive DB lookup as a fallback
                        db_pattern = PaymentPattern.objects.filter(
                            company_id=self.company_id,
                            party_name__iexact=balance.party_name
                        ).first()
                        if db_pattern:
                            key = db_pattern.party_name.lower().strip()
                            self.payment_patterns[key] = {
                                'avg_delay': int(db_pattern.avg_payment_days or 30),
                                'avg_payment_days': int(db_pattern.avg_payment_days or 30),
                                'confidence': float(db_pattern.confidence_score or 0.5),
                                'sample_size': int(db_pattern.sample_size or 0),
                                'std_deviation': float(db_pattern.delay_std_deviation or 0)
                            }
                            pattern = self.payment_patterns.get(key)
                        else:
                            logger.info(f"No payment pattern found for party {balance.party_name}, using fallback pattern")
                            # Use a conservative fallback pattern so we still generate receipts
                            pattern = {'avg_payment_days': 30, 'avg_delay': 30, 'confidence': 0.5, 'sample_size': 0, 'std_deviation': 0}

                    # Get their latest sales transactions
                    try:
                        # First verify if the party has an unpaid balance
                        unpaid_amount = abs(float(balance.current_balance))
                        if unpaid_amount <= 0:
                            logger.info(f"No unpaid amount for party {balance.party_name}")
                            continue

                        # Get all sales transactions, regardless of remaining_amount
                        recent_sales = TallyTransaction.objects.filter(
                            company_id=self.company_id,
                            party_name=balance.party_name,
                            register_type='sales'
                        ).order_by('-date')

                        if not recent_sales.exists():
                            continue

                        # Get matching receipts to calculate actual remaining amounts
                        receipt_totals = TallyTransaction.objects.filter(
                            company_id=self.company_id,
                            party_name=balance.party_name,
                            register_type='receipt',
                            date__lte=timezone.now()
                        ).aggregate(total_receipts=Sum('amount'))

                        total_receipts = float(receipt_totals['total_receipts'] or 0)
                        remaining_to_allocate = unpaid_amount  # This is from party_balance

                        logger.info(f"Processing {balance.party_name} - Balance: {unpaid_amount}, " 
                                  f"Sales: {recent_sales.count()}, Receipts: {total_receipts}")

                        if not recent_sales.exists():
                            logger.warning(f"Found unpaid balance but no sales for {balance.party_name}. Balance: {unpaid_amount}")
                            continue

                        logger.info(f"Processing {balance.party_name} - Unpaid: {unpaid_amount}, Sales found: {recent_sales.count()}")
                        remaining_to_allocate = unpaid_amount
                        
                        # Track already allocated amounts to avoid double counting
                        allocated_sales = []

                        # Start allocating from recent sales
                        for sale in recent_sales:
                            if remaining_to_allocate <= 0:
                                break

                            # For recent sales, allocate full remaining balance first
                            sale_amount = float(sale.amount)
                            allocated_amount = min(sale_amount, remaining_to_allocate)
                            
                            if allocated_amount > 0:
                                allocated_sales.append({
                                    'sale': sale,
                                    'amount': allocated_amount,
                                    'original_amount': sale_amount
                                })
                        # Convert allocated sales into predictions
                        for alloc in allocated_sales:
                            sale = alloc['sale']
                            sale_amount = float(alloc.get('original_amount', sale.amount))
                            allocated_amount = float(alloc.get('amount', 0))
                            if allocated_amount <= 0:
                                continue

                            base_delay = pattern.get('avg_payment_days', pattern.get('avg_delay', 30))
                            amount_factor = min(2.0, max(0.5, sale_amount / (pattern.get('avg_amount', sale_amount) or sale_amount)))
                            adjusted_delay = int(base_delay * amount_factor)
                            predicted_date = sale.date + timedelta(days=adjusted_delay)

                            # Confidence calculation
                            days_old = (current_date - sale.date).days
                            age_factor = max(0.3, min(1.0, 1 - (days_old / 180)))
                            amount_confidence = 1.0 - (abs(amount_factor - 1.0) / 2)
                            pattern_confidence = pattern.get('confidence', 0.5)
                            adjusted_confidence = pattern_confidence * age_factor * amount_confidence

                            if predicted_date >= current_date and predicted_date <= end_date:
                                predictions.append({
                                    'date': predicted_date.strftime('%Y-%m-%d'),
                                    'amount': round(allocated_amount, 2),
                                    'party_name': balance.party_name,
                                    'confidence': round(adjusted_confidence, 2),
                                    'type': 'predicted_receipt',
                                    'sale_reference': getattr(sale, 'voucher_number', ''),
                                    'original_amount': round(sale_amount, 2),
                                    'days_outstanding': days_old,
                                    'original_sale_date': sale.date.strftime('%Y-%m-%d')
                                })

                            remaining_to_allocate -= allocated_amount
                            logger.info(f"Predicted payment for {balance.party_name}: {allocated_amount} on {predicted_date}, confidence: {adjusted_confidence}")
                    except Exception as e:
                        logger.error(f"Error fetching sales for party {balance.party_name}: {str(e)}")
                        continue

                        # Get total unpaid amount from party balance
                        unpaid_amount = abs(float(balance.current_balance))
                        remaining_to_allocate = unpaid_amount
                        
                        # Track already allocated amounts to avoid double counting
                        allocated_sales = []

                        # Process sales starting from most recent
                        allocated_sales = []
                        total_allocated = 0
                        
                        for sale in recent_sales:
                            if remaining_to_allocate <= 0:
                                break

                            sale_amount = float(sale.amount)
                            # Calculate allocated amount based on proportion of total unpaid
                            # and how recent the sale is
                            sale_age = (current_date - sale.date).days
                            if sale_age <= 30:  # Recent sales get priority
                                weight = 1.0
                            else:
                                weight = max(0.2, 1.0 - (sale_age / 365))  # Older sales get less weight
                            
                            weighted_amount = sale_amount * weight
                            allocated_amount = min(weighted_amount, remaining_to_allocate)
                            
                            if allocated_amount > 0:
                                allocated_sales.append({
                                    'sale': sale,
                                    'amount': allocated_amount,
                                    'original_amount': sale_amount,
                                    'weight': weight,
                                    'age_days': sale_age
                                })
                                total_allocated += allocated_amount
                                remaining_to_allocate -= allocated_amount
                                
                                # Calculate prediction details based on party's pattern
                                base_delay = pattern['avg_payment_days']
                            # Adjust delay based on amount size relative to their average transaction
                            amount_factor = min(2.0, max(0.5, sale_amount / (pattern.get('avg_amount', sale_amount) or sale_amount)))
                            adjusted_delay = int(base_delay * amount_factor)
                            
                            predicted_date = sale.date + timedelta(days=adjusted_delay)
                            
                            # Calculate confidence based on multiple factors
                            days_old = (current_date - sale.date).days
                            age_factor = max(0.3, min(1.0, 1 - (days_old / 180)))  # Reduce confidence for older sales
                            amount_confidence = 1.0 - (abs(amount_factor - 1.0) / 2)  # Higher confidence if amount is close to average
                            pattern_confidence = pattern['confidence']
                            adjusted_confidence = pattern_confidence * age_factor * amount_confidence
                            
                            if predicted_date >= current_date and predicted_date <= end_date:
                                predictions.append({
                                    'date': predicted_date.strftime('%Y-%m-%d'),
                                    'amount': round(allocated_amount, 2),
                                    'party_name': balance.party_name,
                                    'confidence': round(adjusted_confidence, 2),
                                    'type': 'predicted_receipt',
                                    'sale_reference': getattr(sale, 'voucher_number', ''),
                                    'original_amount': round(sale_amount, 2),
                                    'days_outstanding': days_old,
                                    'original_sale_date': sale.date.strftime('%Y-%m-%d')
                                })
                            
                            remaining_to_allocate -= allocated_amount
                            
                            # Log the prediction
                            logger.info(f"Predicted payment for {balance.party_name}: {allocated_amount} on {predicted_date}, confidence: {adjusted_confidence}")

                logger.info(f"Generated {len(predictions)} payment predictions")
                payment_predictions = predictions

            except PartyBalance.DoesNotExist as e:
                logger.warning("No party balances found in database")
                payment_predictions = []
            except Exception as e:
                logger.error(f"Error generating predictions: {str(e)}", exc_info=True)
                payment_predictions = []
        
            # Get current outstanding sales
            try:
                outstanding_sales = TallyTransaction.objects.filter(
                    company_id=self.company_id,
                    register_type='sales'
                ).exclude(
                    Q(remaining_amount__lte=0) |  # Exclude fully reconciled sales
                    Q(party_name__in=TallyTransaction.objects.filter(
                        company_id=self.company_id,
                        register_type='receipt',
                        date__lte=current_date,
                        is_reconciled=True
                    ).values('party_name'))
                ).values('date', 'amount', 'party_name', 'remaining_amount')  # Include remaining amount
            except Exception as e:
                print(f"Error getting outstanding sales: {str(e)}")
                outstanding_sales = []
        
            # Initialize predictions list and get bank balance
            predicted_cashflow = []
            bank_balance = 0
            try:
                bank_balance = self.get_current_bank_balance()
            except Exception as e:
                print(f"Error getting bank balance: {str(e)}")
        
            # Start with current bank balance
            running_balance = float(bank_balance)
            predicted_cashflow.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'predicted_balance': round(running_balance, 2),
                'receipts': [],
                'expenses': [],
                'type': 'balance',
            })
        
            # Prepare a map of date to prediction for easy update
            prediction_map = {current_date.strftime('%Y-%m-%d'): predicted_cashflow[0]}
        
            # Add predictions from unpaid sales (future receipts)
            for prediction in payment_predictions:
                predicted_date = datetime.strptime(prediction['date'], '%Y-%m-%d').date()
                if predicted_date <= end_date and predicted_date >= current_date:
                    date_str = predicted_date.strftime('%Y-%m-%d')
                    if date_str not in prediction_map:
                        prediction_map[date_str] = {
                            'date': date_str,
                            'predicted_balance': None,
                            'receipts': [],
                            'expenses': [],
                            'type': 'receipt',
                        }
                    prediction_map[date_str]['receipts'].append({
                        'party': prediction['party_name'],
                        'amount': prediction['amount'],
                        'confidence': prediction['confidence'],
                        'reference': prediction.get('sale_reference', ''),
                        'type': 'predicted_receipt'
                    })
        
            # Add predicted fixed expenses (future payments)
            try:
                for description, expense in self.fixed_expenses.items():
                    try:
                        last_date = datetime.strptime(expense['last_payment_date'], '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        print(f"Error parsing last payment date for {description}, using current date")
                        last_date = current_date
                        
                    interval = int(expense['interval_days'])
                    if interval <= 0:
                        print(f"Invalid interval {interval} for {description}, skipping")
                        continue
                        
                    # Calculate next payment date
                    next_date = last_date
                    while next_date <= current_date:
                        next_date += timedelta(days=interval)
                        
                    # Add future payments
                    while next_date <= end_date:
                        date_str = next_date.strftime('%Y-%m-%d')
                        if date_str not in prediction_map:
                            prediction_map[date_str] = {
                                'date': date_str,
                                'predicted_balance': None,
                                'receipts': [],
                                'expenses': [],
                                'type': 'payment',
                            }
                        prediction_map[date_str]['expenses'].append({
                            'description': description,
                            'amount': -round(float(expense['amount']), 2),
                            'confidence': round(float(expense.get('confidence', expense.get('pattern_consistency', 1.0))), 2)
                        })
                        next_date += timedelta(days=interval)
            except Exception as e:
                print(f"Error processing fixed expenses: {str(e)}")
        
            # Calculate running predicted balance for each date
            sorted_dates = sorted(prediction_map.keys())
            total_receipts = 0
            total_expenses = 0
            total_outstanding = 0
            
            # Calculate total outstanding from party balances
            try:
                total_outstanding = abs(float(PartyBalance.objects.filter(
                    company_id=self.company_id,
                    current_balance__lt=0
                ).aggregate(total=Sum('current_balance'))['total'] or 0))
            except Exception as e:
                logger.error(f"Error calculating total outstanding: {str(e)}")
                total_outstanding = 0
            
            for i, date_str in enumerate(sorted_dates):
                if i == 0:
                    continue  # First date already set
                prev_balance = predicted_cashflow[-1]['predicted_balance']
                receipts_total = sum(r['amount'] for r in prediction_map[date_str]['receipts'])
                expenses_total = sum(e['amount'] for e in prediction_map[date_str]['expenses'])
                total_receipts += receipts_total
                total_expenses += abs(expenses_total)
                new_balance = round(prev_balance + receipts_total + expenses_total, 2)
                prediction_map[date_str]['predicted_balance'] = new_balance
                predicted_cashflow.append(prediction_map[date_str])
        
            # Prepare the response data structure
            response_data = {
                'data': {
                    'company_id': str(self.company_id),
                    'predictions': predicted_cashflow[:200],
                    'initial_balance': round(float(bank_balance), 2),
                    'lastUpdated': timezone.now().isoformat(),
                    'dataPoints': {
                        'totalPredictions': len([p for p in predicted_cashflow if p['receipts'] or p['expenses']]),
                        'totalParties': len(self.payment_patterns),
                        'fixedExpenses': len(self.fixed_expenses)
                    },
                    'insights': {
                        'total_expected_receipts': round(total_receipts, 2),
                        'total_expected_expenses': round(total_expenses, 2),
                        'net_cashflow': round(total_receipts - total_expenses, 2)
                    }
                },
                'status': 'success'
            }
            return response_data
        except Exception as e:
            print(f"Error in predict_future_payments: {str(e)}")
            return {}

    def get_current_bank_balance(self):
        """Get the latest bank balance"""
        try:
            if not self.company_id:
                logger.error("Error: company_id is not set")
                return 0

            # First try to get from BankBalance model
            latest_balance = BankBalance.objects.filter(
                company_id=self.company_id
            ).order_by('-updated_at').first()
            
            if latest_balance:
                return float(latest_balance.balance)
                
            # If no bank balance record exists, calculate from transactions
            try:
                transactions = TallyTransaction.objects.filter(
                    company_id=self.company_id,
                    date__lte=timezone.now()
                )
                
                total = 0
                for trans in transactions:
                    if trans.register_type == 'receipt':
                        total += float(trans.amount)
                    elif trans.register_type == 'payment':
                        total -= float(trans.amount)
                        
                # Create a new bank balance record
                BankBalance.objects.create(
                    company_id=self.company_id,
                    balance=total,
                    account_name='default'
                )
            except Exception as e:
                logger.error(f"Error calculating balance from transactions: {str(e)}")
                total = 0
                
            return total
            
        except Exception as e:
            logger.error(f"Error getting bank balance: {str(e)}")
            # Return 0 instead of None to allow predictions to continue
            return 0
