from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import uuid

from transactions.models import TallyTransaction, TransactionMatching
from accounts.models import Company
from transactions.data_processor import normalize_transactions


class Command(BaseCommand):
    help = "Create sample receipt before sale, run normalization, and print results"

    def add_arguments(self, parser):
        parser.add_argument('--company-id', dest='company_id', type=int, help='Company ID to use')
        parser.add_argument('--company-name', dest='company_name', type=str, help='Company name to use')
        parser.add_argument('--cleanup', action='store_true', help='Delete created test records after run')

    def handle(self, *args, **options):
        company = None
        company_id = options.get('company_id')
        company_name = options.get('company_name')
        cleanup = options.get('cleanup')

        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                self.stderr.write(f'Company with id={company_id} not found')
                return
        elif company_name:
            try:
                company = Company.objects.filter(name__icontains=company_name).first()
            except Exception:
                company = None

        if not company:
            company = Company.objects.first()

        if not company:
            self.stderr.write('No Company found in DB. Create one or pass --company-id / --company-name')
            return

        self.stdout.write(f'Using company: {company} (id={company.id})')

        # Create receipt earlier than sale
        today = timezone.now().date()
        receipt_date = today - timedelta(days=10)
        sale_date = today

        party = f'TestParty-{uuid.uuid4().hex[:6]}'

        receipt = TallyTransaction.objects.create(
            company=company,
            voucher_type='Receipt',
            voucher_number=f'RCT-{uuid.uuid4().hex[:8]}',
            date=receipt_date,
            amount=Decimal('1000.00'),
            remaining_amount=Decimal('1000.00'),
            party_name=party,
            register_type='receipt',
            is_reconciled=False
        )

        sale = TallyTransaction.objects.create(
            company=company,
            voucher_type='Sales',
            voucher_number=f'SAL-{uuid.uuid4().hex[:8]}',
            date=sale_date,
            amount=Decimal('1000.00'),
            remaining_amount=Decimal('1000.00'),
            party_name=party,
            register_type='sales',
            is_reconciled=False
        )

        self.stdout.write('Created test transactions:')
        self.stdout.write(f'  Receipt id={receipt.id} date={receipt.date} amount={receipt.amount} party={receipt.party_name}')
        self.stdout.write(f'  Sale    id={sale.id} date={sale.date} amount={sale.amount} party={sale.party_name}')

        # Run normalization which should match receipt <-> sale even if receipt is earlier
        self.stdout.write('Running normalize_transactions...')
        try:
            processed = normalize_transactions(company.id)
            self.stdout.write(f'normalize_transactions returned: {processed}')
        except Exception as e:
            self.stderr.write(f'Error running normalize_transactions: {e}')
            return

        # Refresh from DB
        receipt.refresh_from_db()
        sale.refresh_from_db()

        self.stdout.write('After normalization:')
        self.stdout.write(f'  Receipt remaining_amount={receipt.remaining_amount} is_reconciled={receipt.is_reconciled}')
        self.stdout.write(f'  Sale    remaining_amount={sale.remaining_amount} is_reconciled={sale.is_reconciled}')

        matches = TransactionMatching.objects.filter(source_transaction__in=[sale], target_transaction__in=[receipt])
        if matches.exists():
            for m in matches:
                self.stdout.write(f'  Match: sale_id={m.source_transaction_id} receipt_id={m.target_transaction_id} matched_amount={m.matched_amount} delay_days={m.delay_days}')
        else:
            self.stdout.write('  No TransactionMatching records found between the created sale and receipt.')

        if cleanup:
            self.stdout.write('Cleaning up created test records...')
            try:
                matches.delete()
            except Exception:
                pass
            try:
                receipt.delete()
                sale.delete()
            except Exception:
                pass
            self.stdout.write('Cleanup complete.')
