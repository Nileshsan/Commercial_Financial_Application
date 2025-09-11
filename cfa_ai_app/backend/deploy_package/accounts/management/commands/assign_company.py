from django.core.management.base import BaseCommand
from accounts.models import Company, UserCompany, TallyTransaction
from django.db import transaction

class Command(BaseCommand):
    help = 'Assigns a company to all TallyTransaction records that have no company assigned'

    def add_arguments(self, parser):
        parser.add_argument('company_name', type=str, help='Name of the company to assign transactions to')
        parser.add_argument('user_company_name', type=str, help='Name of the user company (parent company)')

    def handle(self, *args, **options):
        company_name = options['company_name']
        user_company_name = options['user_company_name']

        # Create UserCompany if it doesn't exist
        user_company, created = UserCompany.objects.get_or_create(
            name=user_company_name,
            defaults={'address': ''}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created new UserCompany: {user_company_name}'))

        # Create Company if it doesn't exist
        company, created = Company.objects.get_or_create(
            name=company_name,
            user_company=user_company,
            defaults={'address': ''}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created new Company: {company_name}'))

        # Count transactions with no company
        count_before = TallyTransaction.objects.filter(company__isnull=True).count()
        self.stdout.write(f'Found {count_before} transactions with no company assigned')

        if count_before > 0:
            # Update all transactions that have no company assigned
            with transaction.atomic():
                updated = TallyTransaction.objects.filter(
                    company__isnull=True
                ).update(company=company)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully updated {updated} transactions with company {company_name}'
                    )
                )
        else:
            self.stdout.write(self.style.WARNING('No transactions found needing update'))

        # Verify the update
        count_after = TallyTransaction.objects.filter(company__isnull=True).count()
        self.stdout.write(f'Transactions still without company: {count_after}')
