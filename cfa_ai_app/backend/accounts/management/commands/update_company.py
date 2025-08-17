from django.core.management.base import BaseCommand
from accounts.models import Company, UserCompany, TallyTransaction
from django.db import transaction

class Command(BaseCommand):
    help = 'Updates all TallyTransaction records to a specific company'

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

        # Count all transactions
        total_count = TallyTransaction.objects.count()
        self.stdout.write(f'Found {total_count} total transactions')

        if total_count > 0:
            # Update ALL transactions to the new company
            with transaction.atomic():
                updated = TallyTransaction.objects.all().update(company=company)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully updated {updated} transactions to company {company_name}'
                    )
                )
        else:
            self.stdout.write(self.style.WARNING('No transactions found in the database'))

        # Verify the update
        unassigned = TallyTransaction.objects.filter(company__isnull=True).count()
        assigned_to_company = TallyTransaction.objects.filter(company=company).count()
        self.stdout.write(f'Transactions without company: {unassigned}')
        self.stdout.write(f'Transactions assigned to {company_name}: {assigned_to_company}')
