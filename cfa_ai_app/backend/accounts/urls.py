from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .payment_analysis_views import PaymentAnalysisView, UnpaidSalesView
from .views import (
    TallyDataImportView, TransactionUploadView,
    get_client_transactions, get_clients_summary,
    receive_opening_balances, login_view, logout_view,
    get_user_api_token
)
from .views.profile_view import profile_view
from .views.edit_profile_view import edit_profile
from .views.client_views import ClientRegistrationViewSet
from .views.web_views import (
    ClientListView, ClientCreateView,
    ClientDetailView, ClientUpdateView
)
from .views.home_view import HomeView
from .views import exchange_google_code
from .party_analysis import PartyTransactionAnalysisView
from transactions.model_training import model_status, train_model  # Updated import path
from .payment_prediction_views import (
    analyze_party_payment_behavior, 
    get_payment_predictions, 
    manage_bank_balance,
    get_unpaid_sales,
    get_party_balances,
    get_payment_analysis_summary,
    check_data_status  # Add the new endpoint
)
from .transactions import normalize_transactions
from .urls_cashflow import urlpatterns as cashflow_urls
from transactions.views_api import CashflowViewSet

# Create a router for viewsets
router = DefaultRouter()
router.register(r'tally-import', TallyDataImportView, basename='tally-import')
router.register(r'api/clients', ClientRegistrationViewSet, basename='client-registration')
# Register the Cashflow viewset so action endpoints like update_party_balance
# and get_party_analysis are available at /transactions/cashflow/<company_id>/...
router.register(r'transactions/cashflow', CashflowViewSet, basename='cashflow')

urlpatterns = [
    # Web Views
    path('home/', HomeView.as_view(), name='home'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('clients/', ClientListView.as_view(), name='client_list'),
    path('clients/register/', ClientCreateView.as_view(), name='client_register'),
    path('clients/<int:pk>/', ClientDetailView.as_view(), name='client_detail'),
    path('clients/<int:pk>/edit/', ClientUpdateView.as_view(), name='client_update'),
    # Authentication endpoints
        path('login/', login_view, name='api_login'),
        path('logout/', logout_view, name='api_logout'),
        path('transactions/normalize-transactions/', normalize_transactions, name='normalize-transactions'),
    
    # Router URLs (includes tally-import endpoints)
        path('', include(router.urls)),
    
    # API Token and Model endpoints
        path('user/api-token/', get_user_api_token, name='user_api_token'),
    
# Model status and training endpoints
    path('model/status/', model_status, name='model_status'),  # Updated path using transactions.model_training
    path('model/train/', train_model, name='model_training'),  # Updated path using transactions.model_training    # Transaction endpoints
        path('transactions/', TransactionUploadView.as_view(), name='receive_transactions'),
        path('transactions/<str:client_name>/', get_client_transactions, name='client_transactions'),
        path('clients/summary/', get_clients_summary, name='clients_summary'),
        path('opening-balances/', receive_opening_balances, name='receive_opening_balances'),
        path('party-analysis/', PartyTransactionAnalysisView.as_view(), name='party_analysis'),
    
    # Payment analysis and prediction endpoints
    # Support both query param and URL param patterns for backward compatibility
        path('unpaid-sales/', UnpaidSalesView.as_view(), name='unpaid_sales_query'),
        path('unpaid-sales/<str:company_id>/', UnpaidSalesView.as_view(), name='unpaid_sales'),
        path('party-balances/', get_party_balances, name='party_balances_query'),
        path('party-balances/<str:company_id>/', get_party_balances, name='party_balances'),
        path('payment-analysis-summary/', PaymentAnalysisView.as_view(), name='payment_analysis_summary_query'),
        path('payment-analysis-summary/<str:company_id>/', PaymentAnalysisView.as_view(), name='payment_analysis_summary'),
        path('payment-behavior/<str:party_name>/', analyze_party_payment_behavior, name='payment_behavior'),
        # Support both paths for payment predictions
        path('payment-predictions/', get_payment_predictions, name='payment_predictions'),
        path('api/payment-predictions/', get_payment_predictions, name='payment_predictions_api'),
        path('data-status/', check_data_status, name='data-status'),
        path('bank-balance/', manage_bank_balance, name='bank_balance'),
        # OAuth helper for development: exchange Google auth code for tokens
        path('auth/google/exchange_code/', exchange_google_code, name='exchange_google_code'),
]
urlpatterns += cashflow_urls