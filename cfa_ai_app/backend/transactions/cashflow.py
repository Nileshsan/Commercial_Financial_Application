from django.core.cache import cache
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging
from .models import TallyTransaction, BankBalance, FixedExpense, PaymentPattern
from .payment_analysis import PaymentPatternAnalyzer

logger = logging.getLogger('cfa.cashflow')

class BankBalanceCache:
    """Cache manager for bank balances"""
    
    @staticmethod
    def _get_cache_key(company_id: int, bank_account: str, date: datetime.date) -> str:
        """Generate cache key for bank balance"""
        return f"bank_balance:{company_id}:{bank_account}:{date.isoformat()}"

    @staticmethod
    def set_balance(company_id: int, bank_account: str, balance: Decimal, date: datetime.date = None) -> None:
        """Set bank balance in cache and database"""
        if date is None:
            date = datetime.now().date()
        
        # Update or create BankBalance record
        BankBalance.objects.update_or_create(
            company_id=company_id,
            account_name=bank_account,
            defaults={'balance': balance}
        )
        
        # Update cache
        cache_key = BankBalanceCache._get_cache_key(company_id, bank_account, date)
        cache.set(cache_key, str(balance), timeout=60*60*24)  # Cache for 24 hours

    @staticmethod
    def get_balance(company_id: int, bank_account: str, date: datetime.date = None) -> Decimal:
        """Get bank balance from cache or database"""
        if date is None:
            date = datetime.now().date()
        
        # Try cache first
        cache_key = BankBalanceCache._get_cache_key(company_id, bank_account, date)
        balance = cache.get(cache_key)
        
        if balance is not None:
            return Decimal(balance)
            
        # If not in cache, try database
        try:
            bank_balance = BankBalance.objects.get(
                company_id=company_id,
                account_name=bank_account
            )
            balance = str(bank_balance.balance)
            # Update cache
            cache.set(cache_key, balance, timeout=60*60*24)
            return Decimal(balance)
        except BankBalance.DoesNotExist:
            return None

class CashflowPrediction:
    """Calculate predicted cashflow based on current balance, patterns and fixed expenses"""
    
    def __init__(self, company_id: int):
        self.company_id = company_id
        self.analyzer = PaymentPatternAnalyzer(company_id)
        self.current_date = timezone.now().date()
        
    def calculate_debtor_balances(self, as_of_date: datetime.date = None) -> dict:
        """Calculate remaining balances for all debtors"""
        if as_of_date is None:
            as_of_date = self.current_date

        try:
            # Get all sales and receipts up to the given date
            sales_query = TallyTransaction.objects.filter(
                company_id=self.company_id,
                register_type='sales',
                date__lte=as_of_date
            ).values('party_name', 'date', 'amount')
            
            receipts_query = TallyTransaction.objects.filter(
                company_id=self.company_id,
                register_type='receipt',
                date__lte=as_of_date
            ).values('party_name', 'date', 'amount')

            # Convert to list for faster processing
            sales = list(sales_query)
            receipts = list(receipts_query)

            # Group by party
            balances = {}
            for sale in sales:
                party_name = sale['party_name']
                if party_name not in balances:
                    balances[party_name] = {
                        'total_sales': Decimal('0'),
                        'total_receipts': Decimal('0'),
                        'last_transaction_date': sale['date']
                    }
                balances[party_name]['total_sales'] += sale['amount']
                balances[party_name]['last_transaction_date'] = max(
                    balances[party_name]['last_transaction_date'],
                    sale['date']
                )

            # Subtract receipts
            for receipt in receipts:
                party_name = receipt['party_name']
                if party_name in balances:
                    balances[party_name]['total_receipts'] += receipt['amount']
                    balances[party_name]['last_transaction_date'] = max(
                        balances[party_name]['last_transaction_date'],
                        receipt['date']
                    )

            # Calculate remaining balances
            remaining_balances = {
                party: {
                    'balance': data['total_sales'] - data['total_receipts'],
                    'last_transaction_date': data['last_transaction_date']
                }
                for party, data in balances.items()
                if data['total_sales'] - data['total_receipts'] > 0
            }

            return remaining_balances

        except Exception as e:
            logger.error(f"Error calculating debtor balances: {str(e)}")
            return {}

    def predict_receipts(self, from_date: datetime.date, to_date: datetime.date) -> list:
        """Predict expected receipts based on payment patterns"""
        try:
            # Analyze payment patterns first
            self.analyzer.analyze_payment_patterns()
            
            # Get all parties with pending balances
            debtor_balances = self.calculate_debtor_balances(from_date)
            predicted_receipts = []

            # For each debtor with a balance
            for party_name, balance_data in debtor_balances.items():
                balance = balance_data['balance']
                last_date = balance_data['last_transaction_date']
                
                if party_name in self.analyzer.payment_patterns:
                    pattern = self.analyzer.payment_patterns[party_name]
                    avg_delay = pattern['avg_delay']
                    confidence = pattern['confidence']
                    
                    # Calculate expected payment date
                    expected_date = last_date + timedelta(days=avg_delay)
                    
                    if from_date <= expected_date <= to_date:
                        predicted_receipts.append({
                            'date': expected_date,
                            'amount': float(balance),
                            'party': party_name,
                            'confidence': confidence,
                            'earliest_date': expected_date - timedelta(days=7),
                            'latest_date': expected_date + timedelta(days=7),
                            'last_transaction_date': last_date
                        })

            return sorted(predicted_receipts, key=lambda x: x['date'])

        except Exception as e:
            logger.error(f"Error predicting receipts: {str(e)}")
            return []

    def get_fixed_expenses(self, from_date: datetime.date, to_date: datetime.date) -> list:
        """Get fixed expenses due in the date range"""
        try:
            # First analyze fixed expenses using the analyzer
            self.analyzer.analyze_fixed_expenses()
            due_expenses = []
            
            # Get recurring expenses from analyzer
            for party_name, expense_data in self.analyzer.fixed_expenses.items():
                amount = expense_data['amount']
                interval = expense_data['interval_days']
                last_date = datetime.strptime(expense_data['last_payment_date'], '%Y-%m-%d').date()
                confidence = expense_data['confidence']
                
                # Calculate next payment date
                next_date = last_date
                while next_date <= to_date:
                    if from_date <= next_date:
                        due_expenses.append({
                            'date': next_date,
                            'amount': float(amount),
                            'description': f"Payment to {party_name}",
                            'party': party_name,
                            'confidence': confidence
                        })
                    next_date += timedelta(days=interval)

            # Get manually entered fixed expenses
            manual_expenses = FixedExpense.objects.filter(
                company_id=self.company_id,
                next_date__gte=from_date,
                next_date__lte=to_date
            )

            for expense in manual_expenses:
                due_expenses.append({
                    'date': expense.next_date,
                    'amount': float(expense.amount),
                    'description': expense.description,
                    'confidence': 1.0  # Manual entries have full confidence
                })

            return sorted(due_expenses, key=lambda x: x['date'])

        except Exception as e:
            logger.error(f"Error getting fixed expenses: {str(e)}")
            return []

    def predict_cashflow(self, days: int = 30):
        """Predict cashflow for the next N days"""
        try:
            from_date = self.current_date
            to_date = from_date + timedelta(days=days)
            
            # Get current bank balance
            try:
                bank_balance = BankBalance.objects.filter(
                    company_id=self.company_id
                ).order_by('-updated_at').first()
                
                if not bank_balance:
                    raise ValueError("Current bank balance not available")
                
                current_balance = float(bank_balance.balance)
            except Exception as e:
                logger.error(f"Error getting bank balance for company {self.company_id}: {str(e)}")
                raise ValueError("Current bank balance not available")
            
            # Get predicted receipts
            receipts = self.predict_receipts(from_date, to_date)
            
            # Get fixed expenses
            expenses = self.get_fixed_expenses(from_date, to_date)
            
            # Calculate daily predicted balances with confidence ranges
            daily_predictions = []
            running_balance = current_balance
            min_balance = current_balance
            max_balance = current_balance
            
            # Create a day-by-day prediction
            for day in range(days + 1):  # Include end date
                current_date = from_date + timedelta(days=day)
                
                # Get receipts for this date
                day_receipts = [r for r in receipts if r['date'] == current_date]
                day_expenses = [e for e in expenses if e['date'] == current_date]
                
                # Calculate different balance scenarios
                receipt_amount = sum(r['amount'] for r in day_receipts)
                expense_amount = sum(e['amount'] for e in day_expenses)
                
                # Calculate confidence-weighted minimum receipt
                min_receipt = sum(r['amount'] * r['confidence'] for r in day_receipts)
                
                # Calculate maximum possible receipt for this date
                max_receipt = sum(
                    r['amount'] 
                    for r in receipts 
                    if r['earliest_date'] <= current_date <= r['latest_date']
                )
                
                # Update running balances
                running_balance += receipt_amount - expense_amount
                min_balance += min_receipt - expense_amount
                max_balance += max_receipt - expense_amount
                
                # Create prediction entry
                prediction = {
                    'date': current_date.strftime('%Y-%m-%d'),
                    'predicted_balance': round(running_balance, 2),
                    'min_balance': round(min_balance, 2),
                    'max_balance': round(max_balance, 2),
                    'receipts': [{
                        'date': r['date'].strftime('%Y-%m-%d'),
                        'amount': round(r['amount'], 2),
                        'party': r['party'],
                        'confidence': round(r['confidence'], 2)
                    } for r in day_receipts],
                    'expenses': [{
                        'date': e['date'].strftime('%Y-%m-%d'),
                        'amount': round(e['amount'], 2),
                        'description': e['description']
                    } for e in day_expenses]
                }
                
                daily_predictions.append(prediction)
            
            return {
                'status': 'success',
                'data': {
                    'predictions': daily_predictions,
                    'summary': {
                        'total_expected_receipts': round(sum(r['amount'] for r in receipts), 2),
                        'total_expected_expenses': round(sum(e['amount'] for e in expenses), 2),
                        'initial_balance': round(current_balance, 2),
                        'final_predicted_balance': round(running_balance, 2),
                        'days_forecast': days
                    }
                }
            }
            
        except ValueError as e:
            logger.error(f"Cashflow prediction error for company {self.company_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in cashflow prediction for company {self.company_id}: {str(e)}")
            return {
                'status': 'error',
                'message': 'An unexpected error occurred while generating predictions'
            }
