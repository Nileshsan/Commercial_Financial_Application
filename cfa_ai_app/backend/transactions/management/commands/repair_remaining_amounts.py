from django.core.management.base import BaseCommand
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F
from transactions.models import TallyTransaction, TransactionMatching


class Command(BaseCommand):
    help = "Detect and optionally repair inconsistent remaining_amount values on TallyTransaction rows"

    def add_arguments(self, parser):
        parser.add_argument('--company-id', dest='company_id', type=int, help='Company ID to operate on')
        parser.add_argument('--limit', dest='limit', type=int, default=100, help='Max rows to report')
        parser.add_argument('--apply', action='store_true', help='Apply fixes instead of dry-run')

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        limit = options.get('limit') or 100
        do_apply = options.get('apply')

        qs = TallyTransaction.objects.all()
        if company_id:
            qs = qs.filter(company_id=company_id)

        # Annotate each transaction with total matched_amount where it is source (outgoing matches)
        src_agg = TransactionMatching.objects.values('source_transaction').annotate(total=Sum('matched_amount'))
        tgt_agg = TransactionMatching.objects.values('target_transaction').annotate(total=Sum('matched_amount'))

        # Build dictionaries for quick lookup
        src_map = {entry['source_transaction']: (entry['total'] or Decimal('0')) for entry in src_agg}
        tgt_map = {entry['target_transaction']: (entry['total'] or Decimal('0')) for entry in tgt_agg}

        # Find transactions where stored remaining_amount differs from computed expected_remaining
        discrepancies = []
        count = 0
        for tx in qs.order_by('created_at'):
            if count >= limit:
                break
            matched_as_source = Decimal(str(src_map.get(tx.id, Decimal('0') or 0)))
            matched_as_target = Decimal(str(tgt_map.get(tx.id, Decimal('0') or 0)))

            # For sales (or opening_balance), expected remaining = amount - sum(matches where this tx is source)
            # For receipts, expected remaining = amount - sum(matches where this tx is target)
            reg = (tx.register_type or '').lower()
            if reg in ['receipt']:
                expected_remaining = (Decimal(tx.amount) - matched_as_target)
            else:
                expected_remaining = (Decimal(tx.amount) - matched_as_source)

            stored = tx.remaining_amount if tx.remaining_amount is not None else Decimal(tx.amount)

            # Normalize to Decimal for comparison
            try:
                stored_d = Decimal(stored)
            except Exception:
                stored_d = Decimal('0')

            # Consider a discrepancy when values differ (allow exact equality only)
            if stored_d != expected_remaining:
                delta = expected_remaining - stored_d
                discrepancies.append({
                    'id': tx.id,
                    'party': tx.party_name,
                    'voucher': tx.voucher_number,
                    'register_type': tx.register_type,
                    'amount': str(tx.amount),
                    'stored_remaining': str(stored_d),
                    'expected_remaining': str(expected_remaining),
                    'delta': str(delta),
                    'created_at': str(tx.created_at)
                })
                count += 1

        if not discrepancies:
            self.stdout.write('No discrepancies found (within limit).')
            return

        self.stdout.write(f'Found {len(discrepancies)} discrepancy(ies) (showing up to {limit}):')
        for d in discrepancies:
            self.stdout.write(f"id={d['id']} party={d['party']} voucher={d['voucher']} reg={d['register_type']} amount={d['amount']} stored_remaining={d['stored_remaining']} expected_remaining={d['expected_remaining']} delta={d['delta']}")

        if do_apply:
            self.stdout.write('\nApplying fixes...')
            applied = 0
            for d in discrepancies:
                tx_id = d['id']
                try:
                    with transaction.atomic():
                        tx = TallyTransaction.objects.select_for_update().get(id=tx_id)
                        new_remaining = Decimal(d['expected_remaining'])
                        tx.remaining_amount = new_remaining
                        tx.is_reconciled = new_remaining <= Decimal('0')
                        tx.save()
                        applied += 1
                except Exception as e:
                    self.stderr.write(f'Failed to apply fix to tx id={tx_id}: {e}')
            self.stdout.write(f'Applied fixes to {applied} transactions.')
        else:
            self.stdout.write('\nDry-run mode. To apply fixes re-run with --apply')
