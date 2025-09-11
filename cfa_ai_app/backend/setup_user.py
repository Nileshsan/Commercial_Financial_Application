import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cfa_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Company, UserCompany

User = get_user_model()

def setup_user():
    # Create or get companies first
    company, _ = Company.objects.get_or_create(
        name="Test Business",
        defaults={
            "gstin": "TEST123456789",
            "address": "Test Address",
            "contact_number": "1234567890"
        }
    )
    print(f"Using Company: {company.name}")
    
    user_company, _ = UserCompany.objects.get_or_create(
        name="Test Company",
        defaults={
            "gstin": "TEST987654321",
            "address": "Test Address",
            "contact_number": "9876543210"
        }
    )
    print(f"Using UserCompany: {user_company.name}")
    
    # Create or update the user
    try:
        user = User.objects.get(username="Nilesh")
        print(f"Found existing user: {user.username}")
    except User.DoesNotExist:
        user = User(
            username="Nilesh",
            email="aienileshsanyasi.pbs@gmail.com",
            is_active=True,
            company=company,
            user_company=user_company
        )
        print("Creating new user: Nilesh")
    
    # Set password and save
    user.set_password("Nilesh23@a")
    user.save()
    print("Password updated")
    
    # Verify user details
    print("\nUser Details:")
    print(f"Username: {user.username}")
    print(f"Email: {user.email}")
    print(f"Is Active: {user.is_active}")
    print(f"Company: {user.company.name if user.company else 'None'}")
    print(f"User Company: {user.user_company.name if user.user_company else 'None'}")
    
    return user, company, user_company

if __name__ == '__main__':
    user, company, user_company = setup_user()
