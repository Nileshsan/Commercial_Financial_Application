from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserCompany, Company

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a test user for authentication testing'

    def handle(self, *args, **options):
        try:
            # Create test user
            username = 'testuser'
            email = 'test@example.com'
            password = 'testpass123'
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.WARNING(f'User {username} already exists')
                )
                return
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Create user company
            user_company, created = UserCompany.objects.get_or_create(
                name='Test User Company'
            )
            
            # Create company
            company, created = Company.objects.get_or_create(
                name='Test Company',
                user_company=user_company
            )
            
            # Associate user with company
            user.user_company = user_company
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created test user:\n'
                    f'Username: {username}\n'
                    f'Password: {password}\n'
                    f'Email: {email}\n'
                    f'Company: {company.name}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating test user: {str(e)}')
            ) 