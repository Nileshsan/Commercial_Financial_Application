from django.contrib import admin
from .models import (
    TallyTransaction, 
    BankBalance, 
    PaymentPattern, 
    FixedExpense,
    PartyBalance,
    LedgerEntry
)

@admin.register(TallyTransaction)
class TallyTransactionAdmin(admin.ModelAdmin):
    list_display = ('company', 'party_name', 'date', 'amount', 'register_type')
    list_filter = ('company', 'register_type', 'date')
    search_fields = ('party_name', 'voucher_number')

@admin.register(BankBalance)
class BankBalanceAdmin(admin.ModelAdmin):
    list_display = ('company', 'account_name', 'balance', 'updated_at')
    list_filter = ('company', 'account_name')

@admin.register(PaymentPattern)
class PaymentPatternAdmin(admin.ModelAdmin):
    list_display = ('company', 'party_name', 'avg_payment_days', 'confidence_score')
    list_filter = ('company',)
    search_fields = ('party_name',)

@admin.register(FixedExpense)
class FixedExpenseAdmin(admin.ModelAdmin):
    list_display = ('company', 'description', 'amount', 'frequency', 'next_date')
    list_filter = ('company', 'frequency', 'is_active')
    search_fields = ('description',)

@admin.register(PartyBalance)
class PartyBalanceAdmin(admin.ModelAdmin):
    list_display = ('company', 'party_name', 'current_balance', 'expected_payment_date')
    list_filter = ('company',)
    search_fields = ('party_name',)

@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'ledger_name', 'amount', 'is_debit', 'is_credit')
    list_filter = ('is_debit', 'is_credit')
    search_fields = ('ledger_name',)
