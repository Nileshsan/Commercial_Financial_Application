import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cfa_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import UserCompany, Company

User = get_user_model()

def create_test_data():
    # Get or create test user company
    user_company, created = UserCompany.objects.get_or_create(
        name="Test Company",
        defaults={"address": "Test Address"}
    )
    print(f"{'Created' if created else 'Using existing'} UserCompany: {user_company.name}")

    # Get or create test company
    company, created = Company.objects.get_or_create(
        name="Test Business",
        user_company=user_company,
        defaults={"address": "Test Business Address"}
    )
    if created:
        company.generate_api_key()
        company.save()
    print(f"{'Created' if created else 'Using existing'} Company: {company.name}")

    # Create test user
    try:
        user = User.objects.get_or_create(
            username="Nilesh",
            email="aienileshsanyasi.pbs@gmail.com",
            defaults={
                'user_company': user_company,
                'company': company,
                'is_staff': True,
                'is_active': True
            }
        )[0]
        user.set_password("Nilesh23@a")
        user.save()
        print(f"Created User: {user.username} (email: {user.email})")
    except Exception as e:
        print(f"Error creating user: {str(e)}")
        # Try to get existing user
        try:
            user = User.objects.get(username="Nilesh")
            print(f"Found existing user: {user.username}")
            user.set_password("Nilesh23@a")
            user.user_company = user_company
            user.company = company
            user.is_active = True
            user.save()
            print("Updated existing user password and company info")
        except User.DoesNotExist:
            print("Could not find or create user")

if __name__ == '__main__':
    create_test_data()
