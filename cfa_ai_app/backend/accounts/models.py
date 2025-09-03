from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _
import binascii
import os

# New model: UserCompany (your client, e.g., Fluidtecq)
class UserCompany(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# New model: Company (business entity belonging to a UserCompany)
class Company(models.Model):
    name = models.CharField(max_length=255)
    user_company = models.ForeignKey(UserCompany, on_delete=models.CASCADE, related_name='companies')
    address = models.TextField(blank=True)
    api_key = models.CharField(max_length=64, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'user_company')

    def __str__(self):
        return f"{self.name} ({self.user_company.name})"
        
    def generate_api_key(self):
        """
        Generate a random API key
        """
        if not self.api_key:
            self.api_key = f"CFA-{binascii.hexlify(os.urandom(16)).decode()}"
        return self.api_key

class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# Payment Analysis Models now live in the transactions app
class LedgerGroup(models.Model):
    """Model to store Tally ledger groups (e.g. Sundry Debtors, Sundry Creditors)"""
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=[
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('other', 'Other')
    ])
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('name', 'company')

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

class LedgerBalance(models.Model):
    """Model to store opening balances for each ledger"""
    ledger_name = models.CharField(max_length=255)
    group = models.ForeignKey(LedgerGroup, on_delete=models.PROTECT)
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2)
    raw_balance = models.CharField(max_length=50)  # Original balance string from Tally
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    synced_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('ledger_name', 'company')

    def __str__(self):
        return f"{self.ledger_name} - {self.opening_balance}"

# Moved to transactions app

# Moved to transactions app

# Moved to transactions app

class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, username, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('employee', 'Employee'),
    ]
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    user_company = models.ForeignKey(UserCompany, on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    client = models.ForeignKey('Client', on_delete=models.SET_NULL, related_name='users', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    is_active = models.BooleanField(default=True)  # type: ignore
    is_staff = models.BooleanField(default=True)  # type: ignore
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.email} ({self.role})"

class BankBalance(models.Model):
    """Model to store daily bank balances"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bank_balances')
    bank_account = models.CharField(max_length=255)  # Bank account name as in Tally
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()
    is_verified = models.BooleanField(default=False)  # Whether this balance was manually verified
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('company', 'bank_account', 'date')
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['company', 'date']),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.bank_account}: {self.balance} ({self.date})"

class FixedExpense(models.Model):
    """Model to store recurring fixed expenses like rent, salary"""
    FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='fixed_expenses')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    due_day = models.IntegerField(help_text="Day of month/quarter/year when payment is due")
    ledger_name = models.CharField(max_length=255, help_text="Corresponding ledger in Tally")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company.name} - {self.description}: {self.amount} ({self.get_frequency_display()})"

# Moved to transactions app

class LedgerOpeningBalance(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='opening_balances')
    ledger_name = models.CharField(max_length=255)
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2)
    group = models.CharField(max_length=255, blank=True)
    raw_balance = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company.name} - {self.ledger_name}: {self.opening_balance}"


# Raw transactions table: append-only copy of incoming Tally sync payloads
class RawTallyTransaction(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    voucher_type = models.CharField(max_length=100)
    voucher_number = models.CharField(max_length=100, blank=True)
    date = models.DateField(null=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    party_name = models.CharField(max_length=255, blank=True)
    register_type = models.CharField(max_length=50, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)
    processed = models.BooleanField(default=False, help_text="Whether this raw row has been normalized into transactions.TallyTransaction")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'voucher_type']),
            models.Index(fields=['company', 'party_name']),
            models.Index(fields=['processed'])
        ]

    def __str__(self):
        return f"RAW {self.company.name} - {self.voucher_type}:{self.voucher_number} ({self.amount})"

# Token model is provided by rest_framework.authtoken
