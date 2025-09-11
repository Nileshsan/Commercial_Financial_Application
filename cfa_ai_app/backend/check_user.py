import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cfa_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

print("\nAll Users in Database:")
print("=====================")
users = User.objects.all()
for user in users:
    print(f"\nUsername: {user.username}")
    print(f"Email: {user.email}")
    print(f"Is Active: {user.is_active}")
    print(f"Company: {user.company.name if user.company else 'None'}")
    print(f"User Company: {user.user_company.name if user.user_company else 'None'}")
    print("=====================")
