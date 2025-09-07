from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    Client, User, Company, LedgerGroup, 
    LedgerBalance, LedgerOpeningBalance
)

class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "user_company", "api_key", "address", "created_at")
    search_fields = ("name", "user_company__name", "api_key")
    list_filter = ("user_company",)
    fields = ("name", "user_company", "api_key", "address")

class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "username", "password", "user_company", "company", "client", "role"),
               "description": "Basic user information and associations"}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
                      "description": "User permissions and access control"}),
        ("Important dates", {"fields": ("last_login", "date_joined"),
                         "description": "Account activity timestamps"}),
    )
    readonly_fields = ("date_joined",)
    list_display = ("email", "username", "user_company", "company", "client", "role", "is_staff", "is_active")
    search_fields = ("email", "username", "user_company__name", "company__name")
    ordering = ("email",)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2", "user_company", "company", "client", "role", "is_staff", "is_active"),
            "description": "Create a new user with basic information and permissions",
        }),
    )

class LedgerGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "company")
    list_filter = ("category", "company")
    search_fields = ("name",)

class LedgerBalanceAdmin(admin.ModelAdmin):
    list_display = ("ledger_name", "group", "opening_balance", "company", "synced_at")
    list_filter = ("group__category", "company")
    search_fields = ("ledger_name",)
    readonly_fields = ("synced_at",)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "company")

class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "created_at")
    search_fields = ("name", "address")
    list_filter = ("created_at",)

class LedgerOpeningBalanceAdmin(admin.ModelAdmin):
    list_display = ("ledger_name", "company", "opening_balance", "group")
    list_filter = ("company", "group")
    search_fields = ("ledger_name", "company__name")
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("company")

# Register all models in a logical order
admin.site.register(Client, ClientAdmin)  # Top-level organization
admin.site.register(User, UserAdmin)      # Users and authentication
admin.site.register(Company, CompanyAdmin) # Business entities
admin.site.register(LedgerGroup, LedgerGroupAdmin)      # Financial records
admin.site.register(LedgerBalance, LedgerBalanceAdmin)
admin.site.register(LedgerOpeningBalance, LedgerOpeningBalanceAdmin)  # Opening balances
