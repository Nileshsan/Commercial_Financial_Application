import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from django.db.models import Q
from django.db import connection
from transactions.models import TallyTransaction, LedgerMaster

class PaymentBehaviorAnalyzer:
    def __init__(self):
        self.payment_patterns = {}
        self.payment_delays = {}
        
    def get_debtors_with_balances(self) -> Dict:
        """Get all debtors with their opening balances"""
        debtors = LedgerMaster.objects.filter(
            group__icontains='Sundry Debtors'
        ).values('ledger_name', 'opening_balance')
        return {d['ledger_name']: d['opening_balance'] for d in debtors}
        
    def calculate_weighted_average_delay(self, party_name: str) -> Dict:
        """
        Calculate weighted average payment delay for a party using both methods:
        1. Exact amount matching
        2. Sequential FIFO matching
        """
        # Get all sales and receipt transactions for the party
        transactions = TallyTransaction.objects.filter(
            Q(party_name=party_name) & 
            Q(register_type__in=['Sales', 'Receipt'])
        ).order_by('date')
        
        if not transactions:
            return {
                'avg_delay': 0,
                'weighted_avg_delay': 0,
                'confidence': 0,
                'matching_pairs': [],
                'remaining_sales': []
            }
            
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(
            transactions.values('date', 'amount', 'register_type', 'voucher_number')
        )
        
        # Method 1: Exact amount matching
        exact_matches = self._find_exact_matches(df)
        
        # Method 2: FIFO sequential matching
        fifo_matches = self._find_fifo_matches(df)
        
        # Combine both methods and calculate weighted average
        all_matches = exact_matches + fifo_matches
        if not all_matches:
            return {
                'avg_delay': 0,
                'weighted_avg_delay': 0,
                'confidence': 0,
                'matching_pairs': [],
                'remaining_sales': self._get_remaining_sales(df)
            }
            
        delays = [match['delay_days'] for match in all_matches]
        amounts = [match['amount'] for match in all_matches]
        
        weighted_avg = np.average(delays, weights=amounts)
        confidence = len(all_matches) / len(df) * 100
        
        return {
            'avg_delay': np.mean(delays),
            'weighted_avg_delay': weighted_avg,
            'confidence': confidence,
            'matching_pairs': all_matches,
            'remaining_sales': self._get_remaining_sales(df)
        }
        
    def _find_exact_matches(self, df: pd.DataFrame) -> List[Dict]:
        """Find exact amount matches between sales and receipts"""
        matches = []
        processed_indices = set()
        
        for idx, row in df.iterrows():
            if idx in processed_indices:
                continue
                
            if row['register_type'] == 'Sales':
                # Look for matching receipt
                receipt_match = df[
                    (df['register_type'] == 'Receipt') & 
                    (df['amount'] == -row['amount']) &
                    (df.index > idx)
                ].iloc[0] if len(df[
                    (df['register_type'] == 'Receipt') & 
                    (df['amount'] == -row['amount']) &
                    (df.index > idx)
                ]) > 0 else None
                
                if receipt_match is not None:
                    delay_days = (receipt_match['date'] - row['date']).days
                    matches.append({
                        'sales_date': row['date'],
                        'receipt_date': receipt_match['date'],
                        'amount': abs(row['amount']),
                        'delay_days': delay_days,
                        'match_type': 'exact'
                    })
                    processed_indices.add(idx)
                    processed_indices.add(receipt_match.name)
                    
        return matches
        
    def _find_fifo_matches(self, df: pd.DataFrame) -> List[Dict]:
        """Find sequential FIFO matches between sales and receipts"""
        matches = []
        sales_queue = []
        
        for _, row in df.iterrows():
            if row['register_type'] == 'Sales':
                sales_queue.append({
                    'date': row['date'],
                    'amount': abs(row['amount']),
                    'remaining': abs(row['amount'])
                })
            elif row['register_type'] == 'Receipt' and sales_queue:
                receipt_amount = abs(row['amount'])
                receipt_date = row['date']
                
                while receipt_amount > 0 and sales_queue:
                    sales = sales_queue[0]
                    amount_matched = min(receipt_amount, sales['remaining'])
                    
                    delay_days = (receipt_date - sales['date']).days
                    matches.append({
                        'sales_date': sales['date'],
                        'receipt_date': receipt_date,
                        'amount': amount_matched,
                        'delay_days': delay_days,
                        'match_type': 'fifo'
                    })
                    
                    receipt_amount -= amount_matched
                    sales['remaining'] -= amount_matched
                    
                    if sales['remaining'] == 0:
                        sales_queue.pop(0)
                        
        return matches
        
    def _get_remaining_sales(self, df: pd.DataFrame) -> List[Dict]:
        """Get list of unpaid sales transactions"""
        sales_balance = 0
        remaining_sales = []
        
        for _, row in df.iterrows():
            if row['register_type'] == 'Sales':
                sales_balance += row['amount']
                remaining_sales.append({
                    'date': row['date'],
                    'amount': row['amount'],
                    'voucher_number': row['voucher_number']
                })
            elif row['register_type'] == 'Receipt':
                sales_balance += row['amount']  # Receipt amounts are negative
                
            # Remove fully paid sales
            if sales_balance == 0:
                remaining_sales = []
                
        return remaining_sales if sales_balance > 0 else []

    def predict_future_payments(self, party_name: str, current_date: datetime) -> List[Dict]:
        """
        Predict future payments based on remaining sales and payment behavior
        """
        # Get payment behavior analysis
        behavior = self.calculate_weighted_average_delay(party_name)
        
        if behavior['weighted_avg_delay'] == 0:
            return []
            
        predictions = []
        for sale in behavior['remaining_sales']:
            predicted_date = sale['date'] + pd.Timedelta(days=behavior['weighted_avg_delay'])
            if predicted_date > current_date:
                predictions.append({
                    'amount': abs(sale['amount']),
                    'predicted_date': predicted_date,
                    'confidence': behavior['confidence'],
                    'original_sale_date': sale['date'],
                    'delay_days': behavior['weighted_avg_delay']
                })
                
        return predictions

    def get_all_party_predictions(self, current_date: datetime) -> Dict[str, List]:
        """
        Get payment predictions for all parties
        """
        debtors = self.get_debtors_with_balances()
        all_predictions = {}
        
        for party_name in debtors.keys():
            predictions = self.predict_future_payments(party_name, current_date)
            if predictions:
                all_predictions[party_name] = {
                    'predictions': predictions,
                    'opening_balance': debtors[party_name]
                }
                
        return all_predictions
