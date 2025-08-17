from django.core.management.base import BaseCommand
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from transactions.models import TallyTransaction, TransactionMatching

class Command(BaseCommand):
    help = 'Normalize and match transactions after Tally sync'

    def handle(self, *args, **options):
        self.stdout.write("Starting transaction normalization...")
        self.normalize_transactions()
        self.stdout.write(self.style.SUCCESS('Successfully normalized transactions'))

    def normalize_transactions(self):
        """Normalize transaction data after sync to match test data structure"""
        
        # Get all unprocessed transactions
        transactions = TallyTransaction.objects.filter(is_reconciled=False)
        self.stdout.write(f"Found {transactions.count()} unprocessed transactions")
        
        # Group by party
        party_transactions = {}
        for tx in transactions:
            party_name = tx.party_name.strip()
            if not party_name:
                continue
                
            if party_name not in party_transactions:
                party_transactions[party_name] = {
                    'sales': [],
                    'receipts': []
                }
                
            # Normalize register type
            reg_type = tx.register_type.lower().strip()
            if reg_type in ['sales', 'sale']:
                tx.register_type = 'sales'
                party_transactions[party_name]['sales'].append(tx)
            elif reg_type in ['receipt', 'rcpt', 'receipts']:
                tx.register_type = 'receipt'
                party_transactions[party_name]['receipts'].append(tx)
                
            # Ensure amount is positive
            if tx.amount < 0:
                tx.amount = abs(tx.amount)
            if not tx.remaining_amount:
                tx.remaining_amount = tx.amount
                
            tx.save()
        
        self.stdout.write(f"Processing {len(party_transactions)} parties")
        
        # Match transactions using FIFO
        for party_name, data in party_transactions.items():
            sales = sorted(data['sales'], key=lambda x: x.date)
            receipts = sorted(data['receipts'], key=lambda x: x.date)
            
            self.stdout.write(f"Processing {party_name}: {len(sales)} sales, {len(receipts)} receipts")
            
            for sale in sales:
                remaining_sale = float(sale.remaining_amount or sale.amount)
                if remaining_sale <= 0:
                    continue
                    
                for receipt in receipts:
                    if receipt.date < sale.date:
                        continue
                        
                    remaining_receipt = float(receipt.remaining_amount or receipt.amount)
                    if remaining_receipt <= 0:
                        continue
                        
                    # Match amounts
                    match_amount = min(remaining_sale, remaining_receipt)
                    if match_amount <= 0:
                        continue
                        
                    with transaction.atomic():
                        # Create transaction matching
                        delay_days = (receipt.date - sale.date).days
                        TransactionMatching.objects.create(
                            source_transaction=sale,
                            target_transaction=receipt,
                            matched_amount=Decimal(str(match_amount)),
                            delay_days=delay_days
                        )
                        
                        # Update remaining amounts
                        sale.remaining_amount = Decimal(str(remaining_sale - match_amount))
                        receipt.remaining_amount = Decimal(str(remaining_receipt - match_amount))
                        
                        # Update reconciliation status
                        sale.is_reconciled = sale.remaining_amount <= 0
                        receipt.is_reconciled = receipt.remaining_amount <= 0
                        
                        sale.save()
                        receipt.save()
                        
                    remaining_sale = float(sale.remaining_amount)
                    if remaining_sale <= 0:
                        break
