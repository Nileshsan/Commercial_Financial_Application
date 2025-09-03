from django.core.management.base import BaseCommand
from transactions.models import TallyTransaction, LedgerEntry

class Command(BaseCommand):
    help = 'Delete all TallyTransaction and related LedgerEntry records.'

    def handle(self, *args, **options):
        confirm = input('Are you sure you want to delete ALL transactions and ledger entries? Type YES to confirm: ')
        if confirm != 'YES':
            self.stdout.write(self.style.WARNING('Aborted. No records deleted.'))
            return
        self.stdout.write('Deleting all LedgerEntry records...')
        le_count, _ = LedgerEntry.objects.all().delete()
        self.stdout.write(f'Deleted {le_count} LedgerEntry records.')
        self.stdout.write('Deleting all TallyTransaction records...')
        txn_count, _ = TallyTransaction.objects.all().delete()
        self.stdout.write(f'Deleted {txn_count} TallyTransaction records.')
        self.stdout.write(self.style.SUCCESS('All transactions and ledger entries deleted.'))
