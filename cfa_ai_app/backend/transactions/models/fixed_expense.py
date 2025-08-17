from django.db import models

class FixedExpense(models.Model):
    company_id = models.IntegerField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ])
    due_day = models.IntegerField()  # Day of month for monthly/quarterly/yearly
    is_active = models.BooleanField(default=True)
    last_paid_date = models.DateField(null=True, blank=True)
    next_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sample_size = models.IntegerField(default=0)
    amount_std_deviation = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interval_days = models.IntegerField(default=30)
    interval_std_deviation = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    pattern_consistency = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = 'transactions_fixedexpense'
        indexes = [
            models.Index(fields=['company_id', 'next_date'])
        ]
