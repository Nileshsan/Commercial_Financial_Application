from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
from transactions.models import TallyTransaction, PaymentPattern, TransactionMatching
from accounts.models import Company

class Command(BaseCommand):
    help = 'Refresh transaction data and payment patterns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='Company ID to refresh (optional)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh even if data exists',
        )
        parser.add_argument(
            '--clear-patterns',
            action='store_true',
            help='Clear existing payment patterns before refresh',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        force = options.get('force')
        clear_patterns = options.get('clear_patterns')

        self.stdout.write(self.style.SUCCESS('=== Transaction Data Refresh ==='))

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
            
            # Check current data
            total_transactions = TallyTransaction.objects.filter(company=company).count()
            self.stdout.write(f'Current transactions: {total_transactions}')

            if total_transactions == 0:
                self.stdout.write(self.style.WARNING('No transactions found for this company'))
                continue

            # Check sales and receipts
            sales_count = TallyTransaction.objects.filter(company=company, register_type='sales').count()
            receipts_count = TallyTransaction.objects.filter(company=company, register_type='receipt').count()
            
            self.stdout.write(f'Sales transactions: {sales_count}')
            self.stdout.write(f'Receipt transactions: {receipts_count}')

            if sales_count == 0 or receipts_count == 0:
                self.stdout.write(self.style.ERROR('❌ Need both sales and receipts for payment pattern analysis'))
                continue

            # Clear existing patterns if requested
            if clear_patterns:
                deleted_patterns = PaymentPattern.objects.filter(company=company).delete()
                self.stdout.write(f'Cleared {deleted_patterns[0]} existing payment patterns')

            # Clear existing transaction matchings
            deleted_matchings = TransactionMatching.objects.filter(
                source_transaction__company=company
            ).delete()
            self.stdout.write(f'Cleared {deleted_matchings[0]} existing transaction matchings')

            # Refresh payment patterns
            self.stdout.write('\n--- Refreshing Payment Patterns ---')
            try:
                from accounts.payment_analysis import PaymentPatternAnalyzer
                analyzer = PaymentPatternAnalyzer(company.id)
                patterns = analyzer.analyze_payment_patterns()
                
                if patterns:
                    self.stdout.write(self.style.SUCCESS(f'✅ Successfully analyzed {len(patterns)} payment patterns'))
                    
                    # Show some examples
                    self.stdout.write('\nSample patterns:')
                    for party, pattern in list(patterns.items())[:5]:
                        self.stdout.write(f'  {party}: {pattern["avg_delay"]} days (confidence: {pattern["confidence"]}, samples: {pattern["sample_size"]})')
                    
                    # Check for high confidence patterns
                    high_confidence = {k: v for k, v in patterns.items() if v['confidence'] >= 0.7}
                    self.stdout.write(f'\nHigh confidence patterns (≥70%): {len(high_confidence)}')
                    
                else:
                    self.stdout.write(self.style.WARNING('⚠️  No payment patterns could be analyzed'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error analyzing payment patterns: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())

            # Check for unpaid sales
            try:
                unpaid_sales = analyzer.detect_unpaid_sales()
                self.stdout.write(f'\nUnpaid sales detected: {len(unpaid_sales)}')
                
                if unpaid_sales:
                    total_unpaid = sum(sale['remaining_amount'] for sale in unpaid_sales)
                    self.stdout.write(f'Total unpaid amount: ₹{total_unpaid:,.2f}')
                    
                    # Show some examples
                    self.stdout.write('\nSample unpaid sales:')
                    for sale in unpaid_sales[:3]:
                        self.stdout.write(f'  {sale["party_name"]}: ₹{sale["remaining_amount"]:,.2f} (Date: {sale["date"]})')
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error detecting unpaid sales: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('\n=== Refresh Complete ===')) 