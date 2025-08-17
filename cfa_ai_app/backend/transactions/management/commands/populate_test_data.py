from django.core.management.base import BaseCommand
from django.utils import timezone
from transactions.models import (
    TallyTransaction, LedgerEntry, PartyBalance, PaymentPattern,
    TransactionMatching, FixedExpense, BankBalance
)
from datetime import datetime, timedelta
from decimal import Decimal
import random

class Command(BaseCommand):
    help = 'Populates test data for transactions and related models'

    def add_arguments(self, parser):
        parser.add_argument('company_id', type=int, help='Company ID to create test data for')

    def handle(self, *args, **options):
        company_id = options['company_id']
        self.company_id = company_id
        
        # Clear existing data for this company
        self.clear_existing_data()
        
        # Create initial bank balance
        BankBalance.objects.create(
            company_id=self.company_id,
            balance=Decimal('1000000'),  # Start with 10L initial balance
            account_name='default'
        )
        
        # Create test parties
        parties = [
            "ABC Electronics",
            "XYZ Supplies",
            "Global Services Ltd",
            "Tech Solutions Inc",
            "Office Supplies Co",
            "Quality Products",
            "Fast Logistics",
            "Prime Materials"
        ]
        
        # Create sales transactions (last 90 days)
        self.create_sales_transactions(parties)
        
        # Create receipt transactions (payments received)
        self.create_receipt_transactions()
        
        # Create fixed expenses
        self.create_fixed_expenses()
        
        self.stdout.write(self.style.SUCCESS('Successfully populated test data'))

    def clear_existing_data(self):
        """Clear existing test data for this company"""
        TallyTransaction.objects.filter(company_id=self.company_id).delete()
        PaymentPattern.objects.filter(company_id=self.company_id).delete()
        FixedExpense.objects.filter(company_id=self.company_id).delete()
        TransactionMatching.objects.filter(
            source_transaction__company_id=self.company_id
        ).delete()
        BankBalance.objects.filter(company_id=self.company_id).delete()

    def create_sales_transactions(self, parties):
        """Create test sales transactions"""
        current_date = timezone.now().date()
        start_date = current_date - timedelta(days=90)
        
        # Create 2-3 sales per party over the period
        for party in parties:
            num_sales = random.randint(2, 3)
            for _ in range(num_sales):
                sale_date = start_date + timedelta(days=random.randint(0, 90))
                amount = Decimal(random.randint(50000, 500000))
                
                TallyTransaction.objects.create(
                    company_id=self.company_id,
                    party_name=party,
                    register_type='sales',
                    amount=amount,
                    date=sale_date,
                    voucher_number=f'INV-{random.randint(1000, 9999)}',
                    remaining_amount=amount
                )

    def create_receipt_transactions(self):
        """Create receipt transactions for some sales"""
        sales = TallyTransaction.objects.filter(
            company_id=self.company_id,
            register_type='sales'
        )
        
        for sale in sales:
            # 70% chance of having a receipt
            if random.random() < 0.7:
                payment_delay = random.randint(15, 45)  # Payment received in 15-45 days
                receipt_date = sale.date + timedelta(days=payment_delay)
                
                if receipt_date <= timezone.now().date():
                    receipt = TallyTransaction.objects.create(
                        company_id=self.company_id,
                        party_name=sale.party_name,
                        register_type='receipt',
                        amount=sale.amount,
                        date=receipt_date,
                        voucher_number=f'REC-{random.randint(1000, 9999)}',
                        remaining_amount=sale.amount
                    )
                    
                    # Calculate delay days
                    delay_days = (receipt_date - sale.date).days
                    
                    # Create transaction matching
                    TransactionMatching.objects.create(
                        source_transaction=sale,
                        target_transaction=receipt,
                        matched_amount=sale.amount,
                        delay_days=delay_days
                    )
                    
                    # Update remaining amounts
                    sale.remaining_amount = Decimal('0')
                    sale.is_reconciled = True
                    sale.save()
                    
                    receipt.remaining_amount = Decimal('0')
                    receipt.is_reconciled = True
                    receipt.save()

    def create_fixed_expenses(self):
        """Create fixed monthly expenses"""
        fixed_expenses = [
            ("Rent", 50000),
            ("Utilities", 25000),
            ("Internet", 5000),
            ("Insurance", 15000),
            ("Office Supplies", 10000),
        ]
        
        current_date = timezone.now().date()
        
        for desc, amount in fixed_expenses:
            # Create fixed expense record first
            payment_day = 5  # Set all fixed expenses to be due on 5th of each month
            next_date = current_date.replace(day=payment_day)
            if next_date <= current_date:
                next_date = (next_date + timedelta(days=32)).replace(day=payment_day)
                
            fixed_expense = FixedExpense.objects.create(
                company_id=self.company_id,
                description=desc,
                amount=amount,
                frequency='monthly',
                interval_days=30,  # Monthly
                pattern_consistency=0.95,  # High consistency for fixed expenses
                due_day=payment_day,
                next_date=next_date
            )
            
            # Create last 3 months of payments to establish pattern
            for i in range(3):
                payment_date = (current_date.replace(day=5) - timedelta(days=30 * i))
                
                TallyTransaction.objects.create(
                    company_id=self.company_id,
                    party_name=desc,
                    register_type='payment',
                    amount=amount,
                    date=payment_date,
                    voucher_number=f'PAY-{random.randint(1000, 9999)}',
                    remaining_amount=Decimal('0'),  # Fully reconciled
                    is_reconciled=True
                )
