from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TransactionViewSet
from .views_api import CashflowViewSet, normalize_transactions
from .views_training_fallback import ModelTrainingViewSet

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet)
router.register(r'cashflow', CashflowViewSet, basename='cashflow')
router.register(r'model', ModelTrainingViewSet, basename='model')

urlpatterns = [
    path('', include(router.urls)),
    path('normalize-transactions/', normalize_transactions, name='normalize-transactions'),
]
