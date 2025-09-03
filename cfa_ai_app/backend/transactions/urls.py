from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TransactionViewSet
from .views_api import CashflowViewSet, normalize_transactions
from accounts.model_training import ModelTrainingView

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet)
router.register(r'cashflow', CashflowViewSet, basename='cashflow')

urlpatterns = [
    path('', include(router.urls)),
    path('normalize-transactions/', normalize_transactions, name='normalize-transactions'),
    path('train-model/', ModelTrainingView.as_view(), name='train-model'),
]
