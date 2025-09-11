from django.db import models
from django.conf import settings
from django.utils import timezone
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

class ClientCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    company = models.ForeignKey(UserCompany, on_delete=models.CASCADE, related_name='client_categories')

    class Meta:
        unique_together = ('name', 'company')
        verbose_name_plural = 'Client categories'

    def __str__(self):
        return self.name

class Client(models.Model):
    CLIENT_TYPES = [
        ('INDIVIDUAL', 'Individual'),
        ('BUSINESS', 'Business'),
        ('CORPORATION', 'Corporation')
    ]
    
    RISK_LEVELS = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk')
    ]

    # Basic Information
    name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255, default="Unknown Company")  # Business/Company name
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True)
    company = models.ForeignKey(UserCompany, on_delete=models.CASCADE, related_name='clients', null=True, blank=True)
    
    # Additional Information
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPES, default='INDIVIDUAL')
    category = models.ForeignKey(ClientCategory, on_delete=models.SET_NULL, null=True, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    
    # Business Information
    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    employee_count = models.IntegerField(blank=True, null=True)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default='LOW')
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # Metadata
    tags = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} ({self.name})"

    class Meta:
        unique_together = ('company', 'tax_number')

class ClientDocument(models.Model):
    DOCUMENT_TYPES = [
        ('ID_PROOF', 'ID Proof'),
        ('ADDRESS_PROOF', 'Address Proof'),
        ('BUSINESS_PROOF', 'Business Proof'),
        ('TAX_DOCUMENT', 'Tax Document'),
        ('OTHER', 'Other')
    ]

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='client_documents/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.client.name}"

class ClientActivity(models.Model):
    ACTIVITY_TYPES = [
        ('CREATED', 'Client Created'),
        ('UPDATED', 'Information Updated'),
        ('STATUS_CHANGE', 'Status Changed'),
        ('DOCUMENT_ADDED', 'Document Added'),
        ('CATEGORY_CHANGE', 'Category Changed')
    ]

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Client activities'

    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.client.name}"




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
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Override PermissionsMixin fields to add related_name
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )

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
