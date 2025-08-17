from django.urls import path
from . import views_cashflow
from .payment_analysis_views import PaymentAnalysisView, UnpaidSalesView

urlpatterns = [
    # Cashflow related endpoints
    path('transactions/cashflow/<int:company_id>/get_cashflow_prediction/', 
         views_cashflow.get_cashflow_prediction, 
         name='get_cashflow_prediction'),
    
    path('transactions/cashflow/<int:company_id>/get_party_balances/', 
         views_cashflow.get_party_balances, 
         name='get_party_balances'),
    
    path('transactions/cashflow/<int:company_id>/get_debtor_balances/', 
         views_cashflow.get_debtor_balances, 
         name='get_debtor_balances'),
    
    path('transactions/cashflow/<int:company_id>/update_bank_balance/', 
         views_cashflow.update_bank_balance, 
         name='update_bank_balance'),
         
    # Payment analysis endpoints
    path('transactions/cashflow/<int:company_id>/payment-analysis/',
         PaymentAnalysisView.as_view(),
         name='payment_analysis'),
         
    path('transactions/cashflow/<int:company_id>/unpaid-sales/',
         UnpaidSalesView.as_view(),
         name='unpaid_sales'),
]
