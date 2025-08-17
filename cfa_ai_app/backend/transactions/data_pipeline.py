from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F, Q
from django.utils import timezone
from .models import (
    TallyTransaction, TransactionMatching, PartyBalance,
    PaymentPattern, FixedExpense
)
from accounts.models import LedgerOpeningBalance
from .data_processor import normalize_transactions
from .payment_analysis import PartyAnalysis
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DataPipeline:
    """
    Handles the complete data processing pipeline from raw Tally data to predictions
    """
    
    def __init__(self, company_id):
        self.company_id = company_id
        
    def process_tally_data(self):
        """
        Main pipeline function to process Tally data
        Returns a dict with processing status and metrics
        """
        try:
            logger.info(f"Starting data pipeline for company {self.company_id}")
            
            # Step 1: Load and validate raw data
            raw_data = TallyTransaction.objects.filter(company_id=self.company_id)
            opening_balances = LedgerOpeningBalance.objects.filter(company_id=self.company_id)
            
            if not raw_data.exists():
                return {
                    'status': 'error',
                    'message': 'No Tally transactions found'
                }
                
            if not opening_balances.exists():
                return {
                    'status': 'error',
                    'message': 'No opening balances found. Please sync opening balances first.'
                }
                
            # Clear existing processed data to avoid duplicates
            PaymentPattern.objects.filter(company_id=self.company_id).delete()
            FixedExpense.objects.filter(company_id=self.company_id).delete()
            PartyBalance.objects.filter(company_id=self.company_id).delete()
            TransactionMatching.objects.filter(
                source_transaction__company_id=self.company_id
            ).delete()
                
            # Step 2: Process transactions by type
            party_data = {}
            
            for transaction in raw_data:
                party_name = transaction.party_name
                if party_name not in party_data:
                    party_data[party_name] = {
                        'sales': [],
                        'receipts': [],
                        'purchases': [],
                        'payments': [],
                        'opening_balance': Decimal('0.00'),
                        'current_balance': Decimal('0.00')
                    }
                
                # Categorize transaction
                if transaction.register_type.lower() in ['sales', 'sale']:
                    party_data[party_name]['sales'].append(transaction)
                elif transaction.register_type.lower() in ['receipt', 'receipts']:
                    party_data[party_name]['receipts'].append(transaction)
                elif transaction.register_type.lower() in ['purchase', 'purchases']:
                    party_data[party_name]['purchases'].append(transaction)
                elif transaction.register_type.lower() in ['payment', 'payments']:
                    party_data[party_name]['payments'].append(transaction)
            
            # Step 3: Calculate balances and match transactions
            with transaction.atomic():
                for party_name, data in party_data.items():
                    # Get opening balance
                    opening_balance = opening_balances.filter(
                        ledger_name=party_name
                    ).first()
                    
                    if opening_balance:
                        data['opening_balance'] = Decimal(opening_balance.opening_balance)
                    
                    # Calculate current balance
                    total_sales = sum(t.amount for t in data['sales'])
                    total_receipts = sum(t.amount for t in data['receipts'])
                    total_purchases = sum(t.amount for t in data['purchases'])
                    total_payments = sum(t.amount for t in data['payments'])
                    
                    # Current balance = Opening + (Sales - Receipts) - (Purchases - Payments)
                    data['current_balance'] = (
                        data['opening_balance'] +
                        (total_sales - total_receipts) -
                        (total_purchases - total_payments)
                    )
                    
                    # Create/Update party balance
                    party_balance = PartyBalance.objects.create(
                        company_id=self.company_id,
                        party_name=party_name,
                        current_balance=data['current_balance'],
                        last_updated=timezone.now()
                    )
                    
                    # Match sales with receipts for payment pattern analysis
                    sales = sorted(data['sales'], key=lambda x: x.date)
                    receipts = sorted(data['receipts'], key=lambda x: x.date)
                    
                    payment_delays = []
                    for sale in sales:
                        remaining = sale.amount
                        for receipt in receipts:
                            if receipt.date >= sale.date and receipt.remaining_amount > 0:
                                # Calculate how much can be allocated
                                allocation = min(remaining, receipt.remaining_amount)
                                if allocation > 0:
                                    # Create transaction matching
                                    delay_days = (receipt.date - sale.date).days
                                    payment_delays.append(delay_days)
                                    
                                    TransactionMatching.objects.create(
                                        source_transaction=sale,
                                        target_transaction=receipt,
                                        matched_amount=allocation,
                                        delay_days=delay_days
                                    )
                                    
                                    remaining -= allocation
                                    receipt.remaining_amount -= allocation
                                    receipt.save()
                                    
                                    if remaining <= 0:
                                        break
                        
                        sale.remaining_amount = remaining
                        sale.save()
                    
                    # Create payment pattern if we have enough data
                    if payment_delays:
                        avg_delay = sum(payment_delays) / len(payment_delays)
                        confidence = min(1.0, len(payment_delays) / 10)  # More samples = higher confidence
                        
                        PaymentPattern.objects.create(
                            company_id=self.company_id,
                            party_name=party_name,
                            avg_payment_days=avg_delay,
                            confidence_score=confidence,
                            sample_size=len(payment_delays),
                            pattern_consistency=confidence,
                            last_analysis_date=timezone.now()
                        )
            
            # Step 4: Analyze payment patterns
            patterns = self._analyze_payment_patterns()
            logger.info(f"Generated payment patterns for {len(patterns)} parties")
            
            # Step 5: Extract fixed expenses
            expenses = self._extract_fixed_expenses()
            logger.info(f"Extracted {len(expenses)} fixed expenses")
            
            # Get final metrics
            processed_transactions = TransactionMatching.objects.filter(
                source_transaction__company_id=self.company_id
            ).count()
            
            pattern_count = PaymentPattern.objects.filter(
                company_id=self.company_id
            ).count()
            
            balance_count = PartyBalance.objects.filter(
                company_id=self.company_id
            ).count()
            
            return {
                'status': 'success',
                'metrics': {
                    'normalized_transactions': processed_transactions,
                    'processed_parties': len(party_data),
                    'payment_patterns': pattern_count,
                    'party_balances': balance_count,
                    'fixed_expenses': len(expenses) if expenses else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _normalize_transactions(self):
        """Normalize raw Tally transactions"""
        return normalize_transactions(self.company_id)
        
    def _process_party_balances(self):
        """Calculate and store party balances"""
        try:
            # Get all unique parties
            parties = TallyTransaction.objects.filter(
                company_id=self.company_id
            ).values_list('party_name', flat=True).distinct()
            
            processed_count = 0
            
            for party_name in parties:
                # Get opening balance
                opening_balance = Decimal('0.00')
                try:
                    ob = LedgerOpeningBalance.objects.filter(
                        company_id=self.company_id,
                        ledger_name=party_name
                    ).first()
                    if ob:
                        opening_balance = ob.opening_balance
                except Exception as e:
                    logger.warning(f"Error getting opening balance for {party_name}: {e}")
                
                # Get all transactions
                sales = TallyTransaction.objects.filter(
                    company_id=self.company_id,
                    party_name=party_name,
                    register_type='sales'
                ).order_by('date')
                
                receipts = TallyTransaction.objects.filter(
                    company_id=self.company_id,
                    party_name=party_name,
                    register_type='receipt'
                ).order_by('date')
                
                # Calculate current balance
                total_sales = sum(sale.amount for sale in sales)
                total_receipts = sum(receipt.amount for receipt in receipts)
                current_balance = opening_balance + total_sales - total_receipts
                
                # Store party balance
                PartyBalance.objects.update_or_create(
                    company_id=self.company_id,
                    party_name=party_name,
                    defaults={
                        'current_balance': current_balance,
                        'last_transaction_date': timezone.now(),
                        'opening_balance': opening_balance
                    }
                )
                processed_count += 1
                
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing party balances: {e}")
            raise
    
    def _analyze_payment_patterns(self):
        """Analyze and store payment patterns"""
        analyzer = PartyAnalysis()
        return analyzer.calculate_payment_patterns(self.company_id)
    
    def _extract_fixed_expenses(self):
        """Extract and store fixed expense patterns"""
        try:
            # Get all payment transactions
            payments = TallyTransaction.objects.filter(
                company_id=self.company_id,
                register_type='payment'
            ).order_by('date', 'party_name')
            
            # Group by party and analyze frequency
            party_payments = {}
            for payment in payments:
                if payment.party_name not in party_payments:
                    party_payments[payment.party_name] = []
                party_payments[payment.party_name].append(payment)
            
            fixed_expenses = []
            
            for party_name, party_txns in party_payments.items():
                if len(party_txns) >= 3:  # Need at least 3 payments to detect pattern
                    amounts = [tx.amount for tx in party_txns]
                    dates = [tx.date for tx in party_txns]
                    
                    # Check if amounts are consistent
                    avg_amount = sum(amounts) / len(amounts)
                    if all(abs(amt - avg_amount) / avg_amount <= 0.1 for amt in amounts):
                        # Check date intervals
                        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                        avg_interval = sum(intervals) / len(intervals)
                        
                        if all(abs(interval - avg_interval) <= 5 for interval in intervals):
                            # This looks like a fixed expense
                            FixedExpense.objects.update_or_create(
                                company_id=self.company_id,
                                description=party_name,
                                defaults={
                                    'amount': avg_amount,
                                    'interval_days': int(avg_interval),
                                    'last_payment_date': max(dates),
                                    'confidence': 0.95,
                                    'is_active': True
                                }
                            )
                            fixed_expenses.append({
                                'description': party_name,
                                'amount': avg_amount,
                                'interval_days': int(avg_interval)
                            })
            
            return fixed_expenses
            
        except Exception as e:
            logger.error(f"Error extracting fixed expenses: {e}")
            raise
