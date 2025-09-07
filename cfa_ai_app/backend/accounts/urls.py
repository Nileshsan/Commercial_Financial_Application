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
from .model_training import ModelTrainingView
from .model_views import model_status, train_model
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

# Create a router for viewsets
router = DefaultRouter()
router.register(r'tally-import', TallyDataImportView, basename='tally-import')
router.register(r'api/clients', ClientRegistrationViewSet, basename='client-registration')

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
    path('api/login/', login_view, name='api_login'),
    path('api/logout/', logout_view, name='api_logout'),
    path('api/transactions/normalize-transactions/', normalize_transactions, name='normalize-transactions'),
    
    # Router URLs (includes tally-import endpoints)
    path('api/', include(router.urls)),
    
    # API Token and Model endpoints
    path('api/user/api-token/', get_user_api_token, name='user_api_token'),
    
    # Model status and training endpoints
    path('api/model/status/', model_status, name='model_status'),  # Updated to match frontend expectation
    path('api/model/train/', train_model, name='model_training'),  # Updated to match frontend expectation
    
    # Transaction endpoints
    path('api/transactions/', TransactionUploadView.as_view(), name='receive_transactions'),
    path('api/transactions/<str:client_name>/', get_client_transactions, name='client_transactions'),
    path('api/clients/summary/', get_clients_summary, name='clients_summary'),
    path('api/opening-balances/', receive_opening_balances, name='receive_opening_balances'),
    path('api/party-analysis/', PartyTransactionAnalysisView.as_view(), name='party_analysis'),
    
    # Payment analysis and prediction endpoints
    # Support both query param and URL param patterns for backward compatibility
    path('api/unpaid-sales/', UnpaidSalesView.as_view(), name='unpaid_sales_query'),
    path('api/unpaid-sales/<str:company_id>/', UnpaidSalesView.as_view(), name='unpaid_sales'),
    path('api/party-balances/', get_party_balances, name='party_balances_query'),
    path('api/party-balances/<str:company_id>/', get_party_balances, name='party_balances'),
    path('api/payment-analysis-summary/', PaymentAnalysisView.as_view(), name='payment_analysis_summary_query'),
    path('api/payment-analysis-summary/<str:company_id>/', PaymentAnalysisView.as_view(), name='payment_analysis_summary'),
    path('api/payment-behavior/<str:party_name>/', analyze_party_payment_behavior, name='payment_behavior'),
    path('api/payment-predictions/', get_payment_predictions, name='payment_predictions'),
    path('api/data-status/', check_data_status, name='data-status'),
    path('api/bank-balance/', manage_bank_balance, name='bank_balance'),
    # OAuth helper for development: exchange Google auth code for tokens
    path('api/auth/google/exchange_code/', exchange_google_code, name='exchange_google_code'),
]
urlpatterns += cashflow_urls