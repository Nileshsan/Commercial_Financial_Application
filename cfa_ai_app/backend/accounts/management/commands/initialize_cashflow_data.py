from django.core.management.base import BaseCommand
from django.db import connection
from accounts.models import Company, Transaction, Party, PaymentPattern, FixedExpense
from django.db.models import Count, Avg
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Initialize and verify cashflow prediction data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Checking required data for cashflow predictions...')
        
        # Check companies
        companies = Company.objects.all()
        for company in companies:
            self.check_company_data(company)
    
    def check_company_data(self, company):
        self.stdout.write(f'\nChecking data for company: {company.name}')
        
        # 1. Check Transactions
        transaction_count = Transaction.objects.filter(company=company).count()
        self.stdout.write(f'Transactions found: {transaction_count}')
        if transaction_count == 0:
            self.stdout.write(self.style.ERROR('No transactions found - Import Tally data first'))
        
        # 2. Check Parties
        party_count = Party.objects.filter(company=company).count()
        self.stdout.write(f'Parties found: {party_count}')
        if party_count == 0:
            self.stdout.write(self.style.ERROR('No parties found - Import Tally data first'))
        
        # 3. Check Payment Patterns
        pattern_count = PaymentPattern.objects.filter(company=company).count()
        self.stdout.write(f'Payment patterns found: {pattern_count}')
        if pattern_count == 0:
            self.stdout.write(self.style.ERROR('No payment patterns - Run pattern analysis'))
        
        # 4. Check Fixed Expenses
        expense_count = FixedExpense.objects.filter(company=company).count()
        self.stdout.write(f'Fixed expenses found: {expense_count}')
        if expense_count == 0:
            self.stdout.write(self.style.WARNING('No fixed expenses configured'))
        
        # 5. Check Transaction Types
        missing_types = Transaction.objects.filter(
            company=company, 
            transaction_type__isnull=True
        ).count()
        if missing_types > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'Found {missing_types} transactions without transaction_type'
                )
            )

        # 6. Analyze Data Quality
        recent_transactions = Transaction.objects.filter(
            company=company,
            date__gte=datetime.now() - timedelta(days=90)
        ).count()
        if recent_transactions == 0:
            self.stdout.write(
                self.style.WARNING('No recent transactions in last 90 days')
            )
        
        # 7. Check Party Classification
        unclassified_parties = Party.objects.filter(
            company=company,
            party_type__isnull=True
        ).count()
        if unclassified_parties > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'Found {unclassified_parties} parties without classification'
                )
            )

        # 8. Verify Payment Pattern Quality
        patterns_without_delay = PaymentPattern.objects.filter(
            company=company,
            avg_payment_delay__isnull=True
        ).count()
        if patterns_without_delay > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'Found {patterns_without_delay} payment patterns without delay calculation'
                )
            )

        # Summary
        self.stdout.write('\nSummary:')
        self.stdout.write(f'Total Transactions: {transaction_count}')
        self.stdout.write(f'Total Parties: {party_count}')
        self.stdout.write(f'Payment Patterns: {pattern_count}')
        self.stdout.write(f'Fixed Expenses: {expense_count}')
        self.stdout.write(f'Recent Transactions: {recent_transactions}')
