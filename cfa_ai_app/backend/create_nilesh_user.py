import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cfa_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Company, UserCompany

User = get_user_model()

# Create companies first - Create UserCompany first since Company needs it
test_user_company = UserCompany.objects.create(
    name="Test Business"
)
print(f"Created user company: {test_user_company.name}")

test_company = Company.objects.create(
    name="Test Company",
    user_company=test_user_company  # Link Company to UserCompany
)
print(f"Created company: {test_company.name}")

# Create user with the specified username and password
user = User.objects.create_user(
    username="Nilesh",
    email="aienileshsanyasi.pbs@gmail.com",
    password="Nilesh23@a",
    company=test_company,
    user_company=test_user_company,
    is_active=True
)

print(f"\nCreated user:")
print(f"Username: {user.username}")
print(f"Email: {user.email}")
print(f"Is Active: {user.is_active}")
print(f"Company: {user.company.name}")
print(f"User Company: {user.user_company.name}")
