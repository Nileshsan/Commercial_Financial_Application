from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F, Q
from django.db.models.functions import Coalesce
from transactions.models import TallyTransaction
from .models import LedgerOpeningBalance
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from transactions.models import PartyBalance
import logging

logger = logging.getLogger(__name__)

class PartyBalanceManager:
    @staticmethod
    def generate_party_balances(company_id):
        """
        Generate or update party balances from transactions
        Returns: (generated_count, updated_count)
        """
        logger.info(f"Generating party balances for company {company_id}")
        
        # Get all parties from transactions
        parties = TallyTransaction.objects.filter(
            company_id=company_id
        ).values_list('party_name', flat=True).distinct()
        
        generated = 0
        updated = 0
        
        for party_name in parties:
            # Calculate balance
            sales = TallyTransaction.objects.filter(
                company_id=company_id,
                party_name=party_name,
                register_type='sales'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            receipts = TallyTransaction.objects.filter(
                company_id=company_id,
                party_name=party_name,
                register_type='receipt'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Get opening balance if exists
            opening_balance = Decimal('0.00')
            try:
                opening = LedgerOpeningBalance.objects.filter(
                    company_id=company_id,
                    ledger_name=party_name
                ).first()
                if opening:
                    opening_balance = opening.opening_balance
            except Exception as e:
                logger.warning(f"Error getting opening balance for {party_name}: {e}")
            
            # Calculate current balance
            current_balance = opening_balance - sales + receipts
            
            # Create or update party balance
            # Only update the essential fields that exist in the model
            balance, created = PartyBalance.objects.update_or_create(
                company_id=company_id,
                party_name=party_name,
                defaults={
                    'current_balance': current_balance,
                    'last_updated': timezone.now()  # Using last_updated instead of last_transaction_date
                }
            )
            if created:
                generated += 1
            else:
                updated += 1
        
        logger.info(f"Party balances for company {company_id}: {generated} generated, {updated} updated")
        return generated, updated
    
    @staticmethod
    def validate_party_balances(company_id):
        """
        Check if party balances exist and are up-to-date
        Returns: (exists, needs_update, message)
        """
        # Check if any party balances exist
        balance_count = PartyBalance.objects.filter(company_id=company_id).count()
        if balance_count == 0:
            return False, True, "No party balances found"
            
        # Check if all parties have balances
        party_count = TallyTransaction.objects.filter(
            company_id=company_id
        ).values('party_name').distinct().count()
        
        if balance_count < party_count:
            return True, True, f"Missing balances for some parties ({balance_count}/{party_count})"
            
        return True, False, "Party balances are up to date"

class PartyTransactionAnalysisView(APIView):
    def get(self, request):
        company_id = request.query_params.get('company_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # Base query for transactions
        transactions = TallyTransaction.objects.filter(company_id=company_id)
        
        if start_date:
            transactions = transactions.filter(date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date__lte=end_date)

        # Group by party and calculate totals
        party_analysis = {}
        
        for transaction in transactions:
            party_name = transaction.party_name
            
            if party_name not in party_analysis:
                party_analysis[party_name] = {
                    'total_sales': 0,
                    'total_purchases': 0,
                    'total_payments': 0,
                    'total_receipts': 0,
                    'transactions': [],
                    'opening_balance': 0,
                    'current_balance': 0
                }
            
            # Get opening balance
            opening_balance = LedgerOpeningBalance.objects.filter(
                company_id=company_id,
                ledger_name=party_name
            ).first()
            
            if opening_balance:
                party_analysis[party_name]['opening_balance'] = float(opening_balance.opening_balance)
            
            # Categorize transaction amounts
            amount = float(transaction.amount)
            if transaction.register_type == 'sales':
                party_analysis[party_name]['total_sales'] += amount
            elif transaction.register_type == 'purchase':
                party_analysis[party_name]['total_purchases'] += amount
            elif transaction.register_type == 'payment':
                party_analysis[party_name]['total_payments'] += amount
            elif transaction.register_type == 'receipt':
                party_analysis[party_name]['total_receipts'] += amount
            
            # Add transaction details
            party_analysis[party_name]['transactions'].append({
                'date': transaction.date,
                'voucher_no': transaction.voucher_no,
                'amount': amount,
                'type': transaction.register_type,
                'narration': transaction.narration
            })

        # Calculate current balance for each party
        for party_name, data in party_analysis.items():
            # For receivables (positive) and payables (negative)
            current_balance = data['opening_balance']
            current_balance += data['total_sales']  # Add sales (increases receivables)
            current_balance -= data['total_receipts']  # Subtract receipts (decreases receivables)
            current_balance -= data['total_purchases']  # Subtract purchases (increases payables)
            current_balance += data['total_payments']  # Add payments (decreases payables)
            
            data['current_balance'] = current_balance
            
            # Sort transactions by date
            data['transactions'].sort(key=lambda x: x['date'])

        return Response({
            'party_analysis': party_analysis,
            'total_parties': len(party_analysis)
        })
