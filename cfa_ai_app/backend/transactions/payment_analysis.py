from datetime import datetime, timedelta
import logging
import numpy as np
import pandas as pd
from django.db import models, transaction
from django.db.models import Avg, F, Q, ExpressionWrapper, DurationField
from django.utils import timezone
from decimal import Decimal
from .models import (
    TallyTransaction,
    BankBalance,
    PaymentPattern,
    TransactionMatching
)            

class PaymentAnalysisError(Exception):
    """Custom exception for payment analysis errors"""
    pass

class PaymentPatternAnalyzer:
    def __init__(self, company_id):
        self.company_id = company_id
        self.payment_patterns = {}
        self.fixed_expenses = {}
        self.logger = logging.getLogger('payment_analysis')
                        
    def _match_transactions_fifo(self, sales, receipts):
        """Match sales to receipts using enhanced FIFO algorithm with weighted delay calculation
        
        Example:
        Sales: 2000 on May 1, 5000 on May 7
        Receipt: 7000 on May 17
        Result: First 2000 matched with 17 days delay, remaining 5000 matched with 10 days delay
        Includes weighted average calculation based on amount
        """
        payment_delays = []
        matched_amount = 0
        receipt_index = 0
        total_weighted_delay = 0
        total_weight = 0
        
        # Ensure transactions are sorted by date
        sales = sorted(sales, key=lambda x: x.date)
        receipts = sorted(receipts, key=lambda x: x.date)
        
        for sale in sales:
            sale_amount = float(sale.remaining_amount or sale.amount)
            if sale_amount <= 0:
                continue
            
            # Track unallocated sale amount
            remaining_sale_amount = sale_amount
            
            # Try to match with receipts that come after this sale
            while remaining_sale_amount > 0 and receipt_index < len(receipts):
                receipt = receipts[receipt_index]
                
                # Skip receipts before sale date
                if receipt.date < sale.date:
                    receipt_index += 1
                    continue
                    
                receipt_amount = float(receipt.remaining_amount or receipt.amount)
                if receipt_amount <= 0:
                    receipt_index += 1
                    continue
                    
                # Calculate matching amount based on remaining amounts
                match_amount = min(remaining_sale_amount, receipt_amount)
                if match_amount > 0:
                    # Update matching and remaining amounts
                    self._update_transaction_matching(sale, receipt, match_amount)
                    
                    delay_days = (receipt.date - sale.date).days
                    payment_delays.append({
                        'days': delay_days,
                        'amount': match_amount,
                        'sale_date': sale.date,
                        'receipt_date': receipt.date
                    })
                    
                    matched_amount += match_amount
                    remaining_sale_amount -= match_amount
                    receipt_amount -= match_amount
                    
                    # If receipt is fully used, move to next one
                    if receipt_amount <= 0:
                        receipt_index += 1
                    
        return payment_delays, matched_amount
    def __init__(self, company_id):
        self.company_id = company_id
        self.payment_patterns = {}
        self.fixed_expenses = {}
        
    def _update_transaction_matching(self, sale, receipt, allocated_amount):
        """Create or update transaction matching records using FIFO"""
        logger = logging.getLogger('payment_analysis')
        try:
            with transaction.atomic():
                # Check if matching already exists
                existing_match = TransactionMatching.objects.filter(
                    source_transaction=sale,
                    target_transaction=receipt
                ).first()
                
                # Calculate delay in days
                delay_days = (receipt.date - sale.date).days
                
                if existing_match:
                    # Update existing match if found
                    existing_match.matched_amount = allocated_amount
                    existing_match.delay_days = delay_days
                    existing_match.save()
                    logger.info(f"Updated matching: Sale {sale.id} to Receipt {receipt.id}, Amount: {allocated_amount}, Delay: {delay_days} days")
                else:
                    # Create new match if not found using FIFO
                    TransactionMatching.objects.create(
                        source_transaction=sale,
                        target_transaction=receipt,
                        matched_amount=allocated_amount,
                        delay_days=delay_days
                    )
                    logger.info(f"Created new matching: Sale {sale.id} to Receipt {receipt.id}, Amount: {allocated_amount}, Delay: {delay_days} days")
                
                # Update remaining amounts using safe conversion
                try:
                    sale.remaining_amount = float(sale.remaining_amount or sale.amount) - allocated_amount
                    receipt.remaining_amount = float(receipt.remaining_amount or receipt.amount) - allocated_amount
                except (TypeError, ValueError) as e:
                    logger.error(f"Error updating remaining amounts: {str(e)}")
                    sale.remaining_amount = float(sale.amount) - allocated_amount
                    receipt.remaining_amount = float(receipt.amount) - allocated_amount
                
                # Update reconciliation status
                sale.is_reconciled = sale.remaining_amount <= 0
                receipt.is_reconciled = receipt.remaining_amount <= 0
                
                sale.save()
                receipt.save()
        except Exception as e:
            print(f"Error in transaction matching: {str(e)}")
            raise
            
    def _save_payment_pattern(self, party_name, pattern_data):
        """Save or update payment pattern in database"""
        PaymentPattern.objects.update_or_create(
            company_id=self.company_id,
            party_name=party_name,
            defaults={
                'avg_payment_days': pattern_data['avg_delay'],
                'confidence_score': pattern_data['confidence'],
                'delay_std_deviation': pattern_data['std_deviation'],
                'pattern_consistency': pattern_data['confidence'],
                'sample_size': pattern_data['sample_size'],
                'last_analysis_date': timezone.now().date()
            }
        )

    def analyze_payment_patterns(self):
        """Calculate weighted average payment delays for each party using FIFO matching"""
        logger = logging.getLogger('payment_analysis')
        logger.info(f"Starting payment pattern analysis for company ID: {self.company_id}")

        # Get all transactions and organize by party and type
        transactions = TallyTransaction.objects.filter(
            company_id=self.company_id,
        ).select_related(
            'company'
        ).order_by('party_name', 'date', 'id')

        # Group transactions by party
        party_transactions = {}
        
        for tx in transactions:
            party_name = tx.party_name.strip()
            if not party_name:
                logger.warning(f"Skipping transaction {tx.id} with empty party name")
                continue

            if party_name not in party_transactions:
                party_transactions[party_name] = {
                    'sales': [],
                    'receipts': [],
                    'total_sales': 0,
                    'total_receipts': 0
                }

            # Normalize register type and amount
            reg_type = tx.register_type.lower().strip()
            try:
                tx_amount = float(tx.amount or 0)
            except (ValueError, TypeError):
                logger.warning(f"Invalid amount for transaction {tx.id}: {tx.amount}")
                tx_amount = 0
                
            # Ensure correct sign based on transaction type
            if reg_type in ['sales', 'sale']:
                if tx_amount < 0:  # Sales should be positive
                    tx_amount = abs(tx_amount)
                party_transactions[party_name]['sales'].append(tx)
                party_transactions[party_name]['total_sales'] += tx_amount
                tx.amount = tx_amount  # Update the amount with correct sign
            elif reg_type in ['receipt', 'receipts', 'rcpt']:
                if tx_amount < 0:  # Receipts should be positive
                    tx_amount = abs(tx_amount)
                party_transactions[party_name]['receipts'].append(tx)
                party_transactions[party_name]['total_receipts'] += tx_amount
                tx.amount = tx_amount  # Update the amount with correct sign

        logger.info(f"Found {len(party_transactions)} parties with transactions")
        
        # Process each party's transactions
        for party_name, data in party_transactions.items():
            sales = data['sales']
            receipts = data['receipts']
            
            logger.info(f"Processing party: {party_name}")
            logger.info(f"Sales: {len(sales)}, Total: {data['total_sales']}")
            logger.info(f"Receipts: {len(receipts)}, Total: {data['total_receipts']}")
            
            if not sales or not receipts:
                logger.warning(f"Skipping party {party_name} - No matching sales({len(sales)}) and receipts({len(receipts)})")
                continue

            # Sort by date (should already be sorted, but ensure)
            sales.sort(key=lambda x: (x.date, x.id))
            receipts.sort(key=lambda x: (x.date, x.id))

            # Initialize tracking variables
            unmatched_sales = []
            current_receipt_idx = 0
            payment_delays = []

            # Process each sale using FIFO with improved matching
            for sale in sales:
                remaining_sale_amount = 0
                try:
                    remaining_sale_amount = abs(float(sale.amount or 0))
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid sale amount for {sale.id}: {sale.amount} - {str(e)}")
                    continue
                    
                sale_matched = False

                if remaining_sale_amount == 0:
                    logger.warning(f"Skipping sale {sale.id} with zero amount")
                    continue

                logger.info(f"Processing sale: ID={sale.id}, Date={sale.date}, Amount={remaining_sale_amount}")

                # Try to match with receipts that come after the sale
                while current_receipt_idx < len(receipts) and remaining_sale_amount > 0:
                    receipt = receipts[current_receipt_idx]
                    remaining_receipt_amount = 0
                    
                    # Initialize/validate receipt amount
                    try:
                        remaining_receipt_amount = abs(float(receipt.remaining_amount or receipt.amount or 0))
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid receipt amount for {receipt.id}: {receipt.amount} - {str(e)}")
                        current_receipt_idx += 1
                        continue

                    # Skip receipts with zero amount
                    if remaining_receipt_amount == 0:
                        current_receipt_idx += 1
                        continue

                    # Skip receipts before the sale date
                    if receipt.date < sale.date:
                        current_receipt_idx += 1
                        continue

                    logger.info(f"Checking receipt: ID={receipt.id}, Date={receipt.date}, Amount={remaining_receipt_amount}")
                    
                    # Calculate the amount to match
                    match_amount = min(remaining_sale_amount, remaining_receipt_amount)
                    
                    if match_amount > 0:
                        # Calculate delay in days
                        delay_days = (receipt.date - sale.date).days
                        
                        try:
                            # Create/update transaction matching
                            self._update_transaction_matching(sale, receipt, match_amount)
                            
                            # Record the delay for pattern analysis
                            payment_delays.append({
                                'days': delay_days,
                                'amount': match_amount,
                                'sale_id': sale.id,
                                'receipt_id': receipt.id
                            })
                            
                            remaining_sale_amount -= match_amount
                            sale_matched = True
                            
                            logger.info(
                                f"Matched: Sale {sale.id} with Receipt {receipt.id}, "
                                f"Amount: {match_amount}, Remaining: {remaining_sale_amount}"
                            )
                        except Exception as e:
                            logger.error(f"Error in transaction matching: {str(e)}")
                            # Continue trying to match other transactions
                            continue
                            
                            logger.debug(
                                f"Matched: Sale {sale.id} ({sale.date}) with "
                                f"Receipt {receipt.id} ({receipt.date}), "
                                f"Amount: {match_amount}, Delay: {delay_days} days"
                            )
                        except Exception as e:
                            logger.error(f"Error matching transactions: {str(e)}")
                    
                    # Move to next receipt if current one is fully used
                    if remaining_receipt_amount <= match_amount:
                        current_receipt_idx += 1

                if not sale_matched:
                    unmatched_sales.append(sale)

            # Calculate payment pattern metrics with validation
            if payment_delays:
                # Calculate total amounts
                total_matched_amount = sum(d['amount'] for d in payment_delays)
                total_sales_amount = sum(float(s.amount or 0) for s in sales)
                total_receipts_amount = sum(float(r.amount or 0) for r in receipts)
                
                # Skip if no significant matches found
                if total_matched_amount < 0.01:  # Threshold to avoid division by zero
                    logger.warning(f"No significant matches found for party {party_name}")
                    continue
                
                # Calculate matching ratio
                sales_matching_ratio = total_matched_amount / total_sales_amount if total_sales_amount else 0
                receipts_matching_ratio = total_matched_amount / total_receipts_amount if total_receipts_amount else 0
                
                logger.info(f"Party {party_name} matching ratios - Sales: {sales_matching_ratio:.2%}, Receipts: {receipts_matching_ratio:.2%}")
                
                # Skip if matching ratio is too low
                if sales_matching_ratio < 0.1 or receipts_matching_ratio < 0.1:  # At least 10% should match
                    logger.warning(f"Low matching ratio for party {party_name} - Skipping pattern analysis")
                    continue
                weighted_delays = sum(d['days'] * d['amount'] for d in payment_delays)
                avg_delay = round(weighted_delays / total_matched_amount)
                
                # Calculate standard deviation of delays
                mean_delay = avg_delay
                squared_diff_sum = sum(
                    ((d['days'] - mean_delay) ** 2) * d['amount'] 
                    for d in payment_delays
                )
                std_deviation = round((squared_diff_sum / total_matched_amount) ** 0.5)

                # Save the pattern
                self._save_payment_pattern(party_name, {
                    'avg_delay': avg_delay,
                    'std_deviation': std_deviation,
                    'sample_size': len(payment_delays),
                    'confidence': min(len(payment_delays) / 10, 1.0),
                    'total_matched': total_matched_amount,
                    'unmatched_sales': len(unmatched_sales)
                })
                
                logger.info(
                    f"Party {party_name}: Avg delay {avg_delay} days, "
                    f"StdDev {std_deviation}, Matches: {len(payment_delays)}, "
                    f"Unmatched: {len(unmatched_sales)}"
                )

        sales_count = sales.count()
        receipts_count = receipts.count()
        
        logger.info(f"Found {sales_count} sales and {receipts_count} receipts")
        
        # Validate amounts
        if sales_count > 0:
            sales_total = sales.aggregate(models.Sum('amount'))['amount__sum'] or 0
            logger.info(f"Total sales amount: {sales_total}")
        if receipts_count > 0:
            receipts_total = receipts.aggregate(models.Sum('amount'))['amount__sum'] or 0
            logger.info(f"Total receipts amount: {receipts_total}")
        
        logger.info(f"Found {sales_count} sales and {receipts_count} receipts")
        
        if sales_count == 0 or receipts_count == 0:
            raise ValueError(
                f"Insufficient transaction data for analysis. "
                f"Sales: {sales_count}, Receipts: {receipts_count}. "
                "Both sales and receipts are required."
            )

        # Get sales transactions
        sales = TallyTransaction.objects.filter(
            company_id=self.company_id,
            register_type='sales'
        ).order_by('date', 'id')  # Ensure consistent ordering

        receipts = TallyTransaction.objects.filter(
            company_id=self.company_id,
            register_type='receipt'
        ).order_by('date', 'id')  # Ensure consistent ordering

        # Convert to DataFrames for easier analysis
        sales_values = sales.values()
        receipts_values = receipts.values()

        if not sales_values or not receipts_values:
            raise ValueError("No matching sales and receipts found for analysis. Sales: {}, Receipts: {}".format(
                len(sales_values), len(receipts_values)
            ))

        sales_df = pd.DataFrame(sales_values)
        receipts_df = pd.DataFrame(receipts_values)

        if 'party_name' not in sales_df.columns:
            return self.payment_patterns  # Return empty patterns if required columns missing

        for party_name in sales_df['party_name'].unique():
            party_sales = sales_df[sales_df['party_name'] == party_name]
            party_receipts = receipts_df[receipts_df['party_name'] == party_name]
            
            delays = []
            weights = []
            
            # Track remaining amounts for each receipt
            receipt_amounts = {}  # {receipt_id: remaining_amount}
            
            # Process each sale in chronological order
            for _, sale_data in party_sales.iterrows():
                sale_amount = float(sale_data['amount'])
                sale_date = pd.to_datetime(sale_data['date']).date()
                remaining_sale = sale_amount
                
                # Get the actual sale model instance
                sale = TallyTransaction.objects.get(id=sale_data['id'])
                
                # Try to match with existing receipts
                for _, receipt_data in party_receipts[party_receipts['date'] >= sale_data['date']].iterrows():
                    if remaining_sale <= 0:
                        break
                        
                    receipt_id = receipt_data['id']
                    receipt_date = pd.to_datetime(receipt_data['date']).date()
                    
                    # Get the actual receipt model instance
                    receipt = TallyTransaction.objects.get(id=receipt_id)
                    
                    # Initialize or get remaining receipt amount using the model instance
                    if receipt_id not in receipt_amounts:
                        receipt_amounts[receipt_id] = float(receipt.remaining_amount or receipt.amount)
                    
                    if receipt_amounts[receipt_id] > 0:
                        # Calculate the amount to allocate
                        allocated = min(remaining_sale, receipt_amounts[receipt_id])
                        receipt_amounts[receipt_id] -= allocated
                        remaining_sale -= allocated
                        
                                    # Calculate delay for this portion
                        delay = (receipt_date - sale_date).days
                        delays.append(delay)
                        weights.append(allocated)  # Weight by the allocated amount
                        
                        # Update transaction matching and remaining amounts
                        self._update_transaction_matching(sale, receipt, allocated)
                
            if delays:
                weighted_avg_delay = np.average(delays, weights=weights)
                confidence = min(len(delays) / 10, 1.0)  # More data points = higher confidence
                
                # Calculate standard deviation of delays for confidence adjustment
                delay_std = np.std(delays) if len(delays) > 1 else 0
                consistency_factor = 1.0 / (1.0 + (delay_std / 30.0))  # Reduce confidence if delays vary widely
                
                pattern_data = {
                    'avg_delay': round(weighted_avg_delay),
                    'confidence': round(confidence * consistency_factor, 2),
                    'sample_size': len(delays),
                    'std_deviation': round(delay_std, 2)
                }
                
                self.payment_patterns[party_name] = pattern_data
                self._save_payment_pattern(party_name, pattern_data)

        return self.payment_patterns

    def analyze_fixed_expenses(self):
        """Identify and analyze fixed/recurring expenses"""
        expenses = TallyTransaction.objects.filter(
            company_id=self.company_id,
            register_type='payment'
        ).order_by('date')

        expenses_values = expenses.values()
        
        if not expenses_values:
            return self.fixed_expenses  # Return empty if no expenses

        expenses_df = pd.DataFrame(expenses_values)
        
        if 'party_name' not in expenses_df.columns or 'date' not in expenses_df.columns:
            return self.fixed_expenses  # Return empty if required columns missing
            
        for party_name in expenses_df['party_name'].unique():
            party_expenses = expenses_df[expenses_df['party_name'] == party_name]
            
            # Check for regular intervals and consistent amounts
            amounts = party_expenses['amount'].astype(float).tolist()
            dates = party_expenses['date'].tolist()
            
            if len(dates) >= 3:  # Need at least 3 transactions to identify pattern
                # Calculate intervals between payments
                intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                avg_interval = np.mean(intervals)
                std_interval = np.std(intervals)
                
                # Calculate amount consistency
                avg_amount = np.mean(amounts)
                std_amount = np.std(amounts)
                
                # If intervals and amounts are consistent (low std dev)
                if std_interval < avg_interval * 0.2 and std_amount < avg_amount * 0.1:
                    self.fixed_expenses[party_name] = {
                        'amount': round(float(avg_amount), 2),
                        'interval_days': round(avg_interval),
                        'confidence': min(len(dates) / 12, 1.0),  # More history = higher confidence
                        'last_payment_date': dates[-1].strftime('%Y-%m-%d')
                    }

        return self.fixed_expenses

    def predict_future_payments(self, days=90):
        """Predict future payments and receipts"""
        current_date = timezone.now().date()
        end_date = current_date + timedelta(days=days)
        
        # Get current outstanding sales
        outstanding_sales = TallyTransaction.objects.filter(
            company_id=self.company_id,
            register_type='sales'
        ).exclude(
            Q(party_name__in=TallyTransaction.objects.filter(
                company_id=self.company_id,
                register_type='receipt',
                date__lte=current_date
            ).values('party_name'))
        ).values('date', 'amount', 'party_name')  # Convert to dict for easier handling

        predicted_cashflow = []
        try:
            bank_balance = self.get_current_bank_balance()
            
            # Start with current bank balance
            predicted_cashflow.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'amount': float(bank_balance),
                'type': 'balance',
                'party': 'Bank',
                'probability': 1.0,
                'is_estimated': bank_balance == 0  # Flag if this is an estimated balance
            })
        except Exception as e:
            print(f"Error processing bank balance: {str(e)}")
            # Continue with predictions even if bank balance is unavailable
            predicted_cashflow.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'amount': 0,
                'type': 'balance',
                'party': 'Bank',
                'probability': 0.5,
                'is_estimated': True
            })
        
        # Predict receipts from outstanding sales
        for sale in outstanding_sales:
            if sale['party_name'] in self.payment_patterns:
                pattern = self.payment_patterns[sale['party_name']]
                predicted_date = sale['date'] + timedelta(days=pattern['avg_delay'])
                
                if predicted_date <= end_date:
                    predicted_cashflow.append({
                        'date': predicted_date.strftime('%Y-%m-%d'),
                        'amount': float(sale['amount']),
                        'type': 'receipt',
                        'party': sale['party_name'],
                        'probability': pattern['confidence']
                    })

        # Add predicted fixed expenses
        for party, expense in self.fixed_expenses.items():
            last_date = datetime.strptime(expense['last_payment_date'], '%Y-%m-%d').date()
            interval = expense['interval_days']
            
            next_date = last_date + timedelta(days=interval)
            while next_date <= end_date:
                predicted_cashflow.append({
                    'date': next_date.strftime('%Y-%m-%d'),
                    'amount': -expense['amount'],  # Negative for expenses
                    'type': 'payment',
                    'party': party,
                    'probability': expense['confidence']
                })
                next_date += timedelta(days=interval)

        return sorted(predicted_cashflow, key=lambda x: x['date'])

    def get_current_bank_balance(self):
        """Get the latest bank balance"""
        try:
            # First try to get from BankBalance model
            latest_balance = BankBalance.objects.filter(
                company_id=self.company_id
            ).order_by('-updated_at').first()
            
            if latest_balance:
                return float(latest_balance.balance)
                
            # If no bank balance record exists, calculate from transactions
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
            
            return total
        except Exception as e:
            print(f"Error getting bank balance: {str(e)}")
            # Return 0 instead of None to allow predictions to continue
            return 0
