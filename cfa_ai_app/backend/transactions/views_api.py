from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management import call_command
from .cashflow import BankBalanceCache, CashflowPrediction
from .payment_analysis import PartyAnalysis
from accounts.models import Company
from .serializers import CashflowPredictionSerializer, PartyBalanceSerializer
from .models import PartyBalance

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def normalize_transactions(request):
    """API endpoint to trigger transaction normalization"""
    try:
        call_command('normalize_transactions')
        return Response({
            'status': 'success',
            'message': 'Transactions normalized successfully'
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CashflowViewSet(viewsets.ViewSet):
    """API endpoints for cashflow predictions and bank balance management"""
    
    @action(detail=True, methods=['post'])
    def update_party_balance(self, request, pk=None):
        """Update party balance and expected payment details from mobile app"""
        try:
            company = Company.objects.get(pk=pk)
            serializer = PartyBalanceSerializer(data=request.data)
            
            if not serializer.is_valid():
                return Response({
                    'status': 'error',
                    'message': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            party_balance, created = PartyBalance.objects.update_or_create(
                company=company,
                party_name=serializer.validated_data['party_name'],
                defaults={
                    'current_balance': serializer.validated_data['current_balance'],
                    'expected_payment_date': serializer.validated_data['expected_payment_date'],
                    'payment_probability': serializer.validated_data['payment_probability']
                }
            )
            
            return Response({
                'status': 'success',
                'message': 'Party balance updated successfully'
            })
            
        except Company.DoesNotExist as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_404_NOT_FOUND)
            
    @action(detail=True, methods=['get'])
    def get_party_balances(self, request, pk=None):
        """Get all party balances with payment expectations"""
        try:
            company = Company.objects.get(pk=pk)
            party_balances = PartyBalance.objects.filter(company=company)
            serializer = PartyBalanceSerializer(party_balances, many=True)
            
            return Response({
                'status': 'success',
                'data': serializer.data
            })
            
        except Company.DoesNotExist as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_404_NOT_FOUND)
            
    @action(detail=True, methods=['get'])
    def get_debtor_balances(self, request, pk=None):
        """Get calculated debtor balances from transactions"""
        try:
            company = Company.objects.get(pk=pk)
            as_of_date = request.query_params.get('as_of_date')
            
            if as_of_date:
                as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
            else:
                as_of_date = datetime.now().date()
                
            balances = CashflowPrediction.calculate_debtor_balances(
                company.id,
                as_of_date=as_of_date
            )
            
            return Response({
                'status': 'success',
                'data': balances
            })
            
        except (Company.DoesNotExist, ValueError) as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def update_bank_balance(self, request, pk=None):
        """Update current bank balance for a company"""
        try:
            company = Company.objects.get(pk=pk)
            balance = Decimal(request.data.get('balance'))
            bank_account = request.data.get('bank_account', 'default')
            
            BankBalanceCache.set_balance(
                company_id=company.id,
                bank_account=bank_account,
                balance=balance
            )
            
            return Response({
                'status': 'success',
                'message': 'Bank balance updated successfully'
            })
            
        except (Company.DoesNotExist, ValueError, TypeError) as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def get_cashflow_prediction(self, request, pk=None):
        """Get cashflow predictions for the next N days"""
        try:
            company = Company.objects.get(pk=pk)
            days = int(request.query_params.get('days', 30))
            bank_account = request.query_params.get('bank_account', 'default')
            
            # Update payment patterns first
            PartyAnalysis.update_payment_patterns(company.id)
            
            # Get predictions
            predictions = CashflowPrediction.predict_cashflow(
                company_id=company.id,
                bank_account=bank_account,
                days=days
            )
            
            return Response({
                'status': 'success',
                'data': {
                    'company': company.name,
                    'predictions': predictions
                }
            })
            
        except (Company.DoesNotExist, ValueError) as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def get_party_analysis(self, request, pk=None):
        """Get payment pattern analysis for a specific party"""
        try:
            company = Company.objects.get(pk=pk)
            party_name = request.query_params.get('party_name')
            
            if not party_name:
                raise ValueError("Party name is required")
            
            pattern = PartyAnalysis.calculate_payment_patterns(
                company_id=company.id,
                party_name=party_name
            )
            
            return Response({
                'status': 'success',
                'data': pattern
            })
            
        except (Company.DoesNotExist, ValueError) as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
