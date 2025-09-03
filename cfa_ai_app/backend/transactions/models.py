from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class BankBalance(models.Model):
    """Model to store current bank balances"""
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    account_name = models.CharField(max_length=255, default='default')
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'account_name']
        indexes = [
            models.Index(fields=['company', 'account_name'])
        ]

    def __str__(self):
        return f"{self.company.name} - {self.account_name}: {self.balance}"

class LedgerMaster(models.Model):
    """Model to store Tally master ledgers and their details"""
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    group = models.CharField(max_length=255)
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    type = models.CharField(max_length=50, choices=[
        ('debtor', 'Debtor'),
        ('creditor', 'Creditor'),
        ('bank', 'Bank'),
        ('cash', 'Cash'),
        ('other', 'Other')
    ])
    last_sync = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'name']
        indexes = [
            models.Index(fields=['company', 'name']),
            models.Index(fields=['company', 'type'])
        ]

    def __str__(self):
        return f"{self.name} ({self.type}) - {self.company.name}"

class PaymentPattern(models.Model):
    """Model to store payment patterns for parties"""
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    party_name = models.CharField(max_length=255)
    avg_payment_days = models.IntegerField(default=30)
    confidence_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0)]
    )
    delay_std_deviation = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0)],
        help_text="Standard deviation of payment delays in days"
    )
    pattern_consistency = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Score indicating how consistent the payment pattern is"
    )
    sample_size = models.IntegerField(
        default=0,
        help_text="Number of transactions used to calculate the pattern"
    )
    expected_payment_date = models.DateField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    last_analysis_date = models.DateField(
        auto_now=True,
        help_text="Date when the pattern was last analyzed"
    )

    class Meta:
        unique_together = ['company', 'party_name']
        indexes = [
            models.Index(fields=['company', 'party_name']),
            models.Index(fields=['expected_payment_date']),
            models.Index(fields=['pattern_consistency'])
        ]

    def __str__(self):
        return f"{self.party_name} - {self.avg_payment_days} days (±{self.delay_std_deviation:.1f})"

class FixedExpense(models.Model):
    """Model to store fixed/recurring expenses"""
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_std_deviation = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Standard deviation of historical payment amounts"
    )
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly')
        ],
        default='monthly'
    )
    interval_days = models.IntegerField(
        default=30,
        help_text="Average interval between payments in days"
    )
    interval_std_deviation = models.FloatField(
        default=0.0,
        help_text="Standard deviation of payment intervals in days"
    )
    pattern_consistency = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Score indicating how consistent the expense pattern is"
    )
    due_day = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Day of the month when payment is due"
    )
    next_date = models.DateField()
    last_paid_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when this expense was last paid"
    )
    sample_size = models.IntegerField(
        default=0,
        help_text="Number of transactions used to identify this pattern"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'next_date']),
            models.Index(fields=['is_active']),
            models.Index(fields=['pattern_consistency'])
        ]

    def __str__(self):
        return f"{self.company.name} - {self.description}: {self.amount}"

class LedgerEntry(models.Model):
    transaction = models.ForeignKey('TallyTransaction', on_delete=models.CASCADE, related_name='ledger_entries')
    ledger_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    is_debit = models.BooleanField()
    is_credit = models.BooleanField()
    def __str__(self):
        return f"{self.ledger_name}: {self.amount} ({'Dr' if self.is_debit else 'Cr'})"

class TallyTransaction(models.Model):
    """Model to store transactions from Tally"""
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    voucher_type = models.CharField(max_length=50)
    voucher_number = models.CharField(max_length=50)
    date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    remaining_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Remaining unpaid amount for sales, or unallocated amount for receipts"
    )
    party_name = models.CharField(max_length=255)
    register_type = models.CharField(
        max_length=50,
        choices=[
            ('sales', 'Sales'),
            ('purchase', 'Purchase'),
            ('receipt', 'Receipt'),
            ('payment', 'Payment'),
            ('journal', 'Journal'),
            ('credit_note', 'Credit Note'),
            ('debit_note', 'Debit Note'),
            ('stock_journal', 'Stock Journal'),
            ('physical_stock', 'Physical Stock'),
            ('manufacturing_journal', 'Manufacturing Journal'),
            ('contra', 'Contra'),
            ('payroll', 'Payroll'),
            ('opening_balance', 'Opening Balance'),
            ('bank_allocation', 'Bank Allocation'),
            ('purchase_order', 'Purchase Order'),
            ('sales_order', 'Sales Order')
        ]
    )
    related_transactions = models.ManyToManyField(
        'self',
        through='TransactionMatching',
        symmetrical=False,
        related_name='linked_transactions',
        help_text="For sales: linked receipts; for receipts: linked sales"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_reconciled = models.BooleanField(
        default=False,
        help_text="Whether this transaction has been fully matched/allocated"
    )

    class Meta:
        unique_together = ['company', 'voucher_type', 'voucher_number']
        indexes = [
            models.Index(fields=['company', 'party_name']),
            models.Index(fields=['date']),
            models.Index(fields=['register_type'])
        ]

    def __str__(self):
        return f"{self.voucher_type} - {self.voucher_number}: {self.amount}"

class TransactionMatching(models.Model):
    """Model to track how sales and receipts are matched"""
    source_transaction = models.ForeignKey(
        TallyTransaction,
        on_delete=models.CASCADE,
        related_name='source_matches'
    )
    target_transaction = models.ForeignKey(
        TallyTransaction,
        on_delete=models.CASCADE,
        related_name='target_matches'
    )
    matched_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Amount allocated from source to target"
    )
    matched_at = models.DateTimeField(auto_now_add=True)
    delay_days = models.IntegerField(
        help_text="Number of days between source and target dates"
    )

    class Meta:
        indexes = [
            models.Index(fields=['source_transaction']),
            models.Index(fields=['target_transaction']),
            models.Index(fields=['matched_at'])
        ]
        unique_together = ['source_transaction', 'target_transaction']

    def __str__(self):
        return f"{self.source_transaction} -> {self.target_transaction}: {self.matched_amount}"

class PartyBalance(models.Model):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    party_name = models.CharField(max_length=255)
    current_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
    )
    last_updated = models.DateTimeField(auto_now=True)
    expected_payment_date = models.DateField(null=True, blank=True)
    payment_probability = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0)]
    )

    class Meta:
        unique_together = ['company', 'party_name']
        indexes = [
            models.Index(fields=['company', 'party_name']),
            models.Index(fields=['expected_payment_date'])
        ]

    def __str__(self):
        return f"{self.party_name} - {self.current_balance}"
