from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Q, Min, Max
from django.utils import timezone
from datetime import datetime, timedelta
from transactions.models import TallyTransaction, PaymentPattern
from accounts.models import Company

class Command(BaseCommand):
    help = 'Check and analyze current transaction data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='Company ID to check (optional)',
        )
        parser.add_argument(
            '--refresh',
            action='store_true',
            help='Refresh payment patterns after checking',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        refresh = options.get('refresh')

        self.stdout.write(self.style.SUCCESS('=== Transaction Data Analysis ==='))

        # Get companies
        if company_id:
            companies = Company.objects.filter(id=company_id)
        else:
            companies = Company.objects.all()

        if not companies.exists():
            self.stdout.write(self.style.ERROR('No companies found'))
            return

        for company in companies:
            self.stdout.write(f'\n--- Company: {company.name} (ID: {company.id}) ---')
            
            # Check total transactions
            total_transactions = TallyTransaction.objects.filter(company=company).count()
            self.stdout.write(f'Total transactions: {total_transactions}')

            if total_transactions == 0:
                self.stdout.write(self.style.WARNING('No transactions found for this company'))
                continue

            # Check by register type
            register_types = TallyTransaction.objects.filter(company=company).values('register_type').annotate(
                count=Count('id'),
                total_amount=Sum('amount')
            )

            self.stdout.write('\nTransactions by type:')
            for rt in register_types:
                self.stdout.write(f'  {rt["register_type"]}: {rt["count"]} transactions, ₹{rt["total_amount"]:,.2f}')

            # Check sales and receipts specifically
            sales_count = TallyTransaction.objects.filter(company=company, register_type='sales').count()
            receipts_count = TallyTransaction.objects.filter(company=company, register_type='receipt').count()
            
            self.stdout.write(f'\nSales transactions: {sales_count}')
            self.stdout.write(f'Receipt transactions: {receipts_count}')

            # Check date range
            date_range = TallyTransaction.objects.filter(company=company).aggregate(
                min_date=Min('date'),
                max_date=Max('date')
            )
            
            if date_range['min_date'] and date_range['max_date']:
                self.stdout.write(f'\nDate range: {date_range["min_date"]} to {date_range["max_date"]}')
                
                # Check if data is recent (within last 6 months)
                six_months_ago = timezone.now().date() - timedelta(days=180)
                if date_range['max_date'] < six_months_ago:
                    self.stdout.write(self.style.WARNING('⚠️  Data appears to be old (more than 6 months)'))
                else:
                    self.stdout.write(self.style.SUCCESS('✅ Data appears to be recent'))

            # Check for parties with both sales and receipts
            parties_with_sales = set(TallyTransaction.objects.filter(
                company=company, register_type='sales'
            ).values_list('party_name', flat=True))
            
            parties_with_receipts = set(TallyTransaction.objects.filter(
                company=company, register_type='receipt'
            ).values_list('party_name', flat=True))
            
            parties_with_both = parties_with_sales.intersection(parties_with_receipts)
            
            self.stdout.write(f'\nParties with sales: {len(parties_with_sales)}')
            self.stdout.write(f'Parties with receipts: {len(parties_with_receipts)}')
            self.stdout.write(f'Parties with both: {len(parties_with_both)}')

            if len(parties_with_both) == 0:
                self.stdout.write(self.style.ERROR('❌ No parties found with both sales and receipts'))
            else:
                self.stdout.write(self.style.SUCCESS(f'✅ Found {len(parties_with_both)} parties with both sales and receipts'))

            # Check existing payment patterns
            existing_patterns = PaymentPattern.objects.filter(company=company).count()
            self.stdout.write(f'\nExisting payment patterns: {existing_patterns}')

            if refresh and len(parties_with_both) > 0:
                self.stdout.write('\n--- Refreshing Payment Patterns ---')
                try:
                    from accounts.payment_analysis import PaymentPatternAnalyzer
                    analyzer = PaymentPatternAnalyzer(company.id)
                    patterns = analyzer.analyze_payment_patterns()
                    
                    if patterns:
                        self.stdout.write(self.style.SUCCESS(f'✅ Successfully analyzed {len(patterns)} payment patterns'))
                        for party, pattern in list(patterns.items())[:5]:  # Show first 5
                            self.stdout.write(f'  {party}: {pattern["avg_delay"]} days (confidence: {pattern["confidence"]})')
                    else:
                        self.stdout.write(self.style.WARNING('⚠️  No payment patterns could be analyzed'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Error analyzing payment patterns: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('\n=== Analysis Complete ===')) 