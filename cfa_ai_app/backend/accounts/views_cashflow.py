from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal
import json
from transactions.cashflow import CashflowPrediction, BankBalanceCache
from transactions.models import TallyTransaction, PaymentPattern, FixedExpense
from .models import Company
from rest_framework.authtoken.models import Token
from .authentication import TokenHeaderAuthentication
import logging

logger = logging.getLogger('cfa.cashflow')

@api_view(['GET'])
@authentication_classes([TokenHeaderAuthentication])
@permission_classes([IsAuthenticated])
def get_cashflow_prediction(request, company_id):
    """Get cashflow prediction for a company"""
    try:
        days = int(request.GET.get('days', 30))

        # Get company and verify access
        try:
            company = Company.objects.get(id=company_id)
            if not company.user_company == request.user.user_company:
                return Response({
                    "status": "error",
                    "message": "Access denied to this company"
                }, status=403)
        except Company.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Company not found"
            }, status=404)

        # Initialize predictor and get prediction
        predictor = CashflowPrediction(company_id)
        result = predictor.predict_cashflow(days=days)
        
        # Return the result
        return Response(result)
    except Exception as e:
        return Response({
            "status": "error",
            "message": str(e)
        }, status=500)

@api_view(['GET'])
@authentication_classes([TokenHeaderAuthentication])
@permission_classes([IsAuthenticated])
def get_party_balances(request, company_id):
    try:
        include_stats = request.GET.get('include_stats', 'true').lower() == 'true'
        real_time = request.GET.get('real_time', 'false').lower() == 'true'

        # Validate company
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Company not found"
            }, status=404)

        # Get party balances from TallyTransaction
        try:
            balances = TallyTransaction.objects.filter(
                company_id=company_id
            ).values('party_name').annotate(
            current_balance=Sum('amount')
        ).order_by('-current_balance')
            
        except Exception as e:
            return Response({
                "status": "error",
                "message": f"Error fetching party balances: {str(e)}"
            }, status=500)

        # Enhance with payment patterns if available
        for balance in balances:
            pattern = PaymentPattern.objects.filter(
                company_id=company_id,
                party_name=balance['party_name']
            ).first()
            
            if pattern:
                balance['expected_payment_date'] = datetime.now().date() + timedelta(days=pattern.avg_payment_days)
                balance['payment_probability'] = pattern.confidence_score
            else:
                balance['expected_payment_date'] = None
                balance['payment_probability'] = 0.5

        return Response({
            "status": "success",
            "data": {
                "balances": list(balances)
            }
        })
    except Exception as e:
        return Response({
            "status": "error",
            "message": str(e)
        }, status=500)

@api_view(['GET'])
@authentication_classes([TokenHeaderAuthentication])
@permission_classes([IsAuthenticated])
def get_debtor_balances(request, company_id):
    try:
        # Get debtor balances from TallyTransaction
        from django.db.models import Sum
        
        debtor_balances = TallyTransaction.objects.filter(
            company_id=company_id,
            register_type='sales'
        ).values('party_name').annotate(
            balance=Sum('amount')
        ).filter(balance__gt=0)

        return Response({
            "status": "success",
            "data": {balance['party_name']: float(balance['balance']) for balance in debtor_balances}
        })
    except Exception as e:
        return Response({
            "status": "error",
            "message": str(e)
        }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_bank_balance(request, company_id):
    try:
        balance = Decimal(request.data.get('balance'))
        bank_account = request.data.get('bank_account', 'default')
        
        if balance is None:
            return Response({
                "status": "error",
                "message": "Balance is required"
            }, status=400)

        BankBalanceCache.set_balance(
            company_id=company_id,
            bank_account=bank_account,
            balance=balance
        )

        return Response({
            "status": "success",
            "message": "Bank balance updated successfully"
        })
    except Exception as e:
        return Response({
            "status": "error",
            "message": str(e)
        }, status=500)
