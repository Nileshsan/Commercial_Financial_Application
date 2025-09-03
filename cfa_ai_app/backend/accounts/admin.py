"""
IMPORTANT: API keys (accounts_token) are linked to users (accounts_user) via user_id.
For sync to work, the user referenced by the API key must have a valid client_id (be associated with a client).
There is no direct link between API key and client; the association is always: API key → user → client.
Assign clients to users in Django admin for proper sync functionality.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.admin import TokenAdmin
from .models import (
    Client, User, Company, LedgerGroup, 
    LedgerBalance, LedgerOpeningBalance
)

class TokenInline(admin.StackedInline):
    model = Token
    can_delete = True
    verbose_name_plural = 'API Tokens'
    max_num = 1

class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_company', 'api_key', 'address', 'created_at')
    search_fields = ('name', 'user_company__name', 'api_key')
    list_filter = ('user_company',)
    fields = ('name', 'user_company', 'api_key', 'address')

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# TallyTransactionAdmin moved to transactions/admin.py

class UserAdmin(BaseUserAdmin):
    inlines = [TokenInline]
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password', 'user_company', 'company', 'client', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    readonly_fields = ('date_joined',)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'user_company', 'company', 'client', 'role', 'is_staff', 'is_active'),
        }),
    )
    list_display = ('email', 'username', 'user_company', 'company', 'client', 'role', 'is_staff', 'is_active')
    search_fields = ('email', 'username')
    ordering = ('email',)

class LedgerGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'company')
    list_filter = ('category', 'company')
    search_fields = ('name',)

class LedgerBalanceAdmin(admin.ModelAdmin):
    list_display = ('ledger_name', 'group', 'opening_balance', 'company', 'synced_at')
    list_filter = ('group__category', 'company')
    search_fields = ('ledger_name',)
    readonly_fields = ('synced_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group', 'company')

# Customize the TokenAdmin
class CustomTokenAdmin(TokenAdmin):
    list_display = ('key', 'user', 'user_company', 'created')
    search_fields = ('user__username', 'user__email', 'key')
    list_filter = ('created',)

    def user_company(self, obj):
        return obj.user.user_company if obj.user else None
    user_company.short_description = 'User Company'

    def save_model(self, request, obj, form, change):
        if not change:  # Only for new tokens
            obj.save()  # This will automatically generate the key

admin.site.register(Client)
admin.site.register(User, UserAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(LedgerGroup, LedgerGroupAdmin)
admin.site.register(LedgerBalance, LedgerBalanceAdmin)

class LedgerOpeningBalanceAdmin(admin.ModelAdmin):
    list_display = ('ledger_name', 'company', 'opening_balance', 'group')
    list_filter = ('company', 'group')
    search_fields = ('ledger_name', 'company__name')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company')

# Register Token with our custom admin
admin.site.register(Token, CustomTokenAdmin)
admin.site.register(LedgerOpeningBalance, LedgerOpeningBalanceAdmin)
