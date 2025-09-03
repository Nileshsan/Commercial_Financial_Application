from django.db.models import Sum, Count
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.models import TallyTransaction
from accounts.mixins import CompanyFilterMixin
from accounts.authentication import CompanyAPIKeyAuthentication

class TransactionViewSet(CompanyFilterMixin, viewsets.ModelViewSet):
    """
    ViewSet for handling TallyTransaction operations.
    All data is automatically filtered by the authenticated company.
    """
    queryset = TallyTransaction.objects.all()
    authentication_classes = [CompanyAPIKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        # Additional filters can be added here
        register_type = self.request.query_params.get('register_type')
        if register_type:
            queryset = queryset.filter(register_type=register_type)
        return queryset

    @action(detail=False, methods=['get'])
    def summary(self):
        """
        Get transaction summary for the company
        """
        queryset = self.get_queryset()
        total_transactions = queryset.count()
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0
        register_summary = (
            queryset.values('register_type')
            .annotate(count=Count('id'), total=Sum('amount'))
        )
        
        return Response({
            'total_transactions': total_transactions,
            'total_amount': total_amount,
            'register_summary': register_summary
        })

    @action(detail=False, methods=['post'])
    def update_bank_balance(self, request):
        """Update bank balance for cashflow predictions"""
        from accounts.models import BankBalance
        
        try:
            balance = request.data.get('balance')
            if balance is None:
                return Response({'status': 'error', 'message': 'Balance is required'}, status=400)
                
            # Get or create bank balance record
            bank_balance, created = BankBalance.objects.update_or_create(
                company=request.user.company,
                account_name='default',
                defaults={'balance': balance}
            )
            
            return Response({
                'status': 'success',
                'message': 'Bank balance updated successfully',
                'data': {
                    'balance': float(bank_balance.balance),
                    'updated_at': bank_balance.updated_at
                }
            })
            
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def get_cashflow_prediction(self, request):
        """Get cashflow predictions"""
        from .payment_analysis import PaymentPatternAnalyzer
        
        try:
            days = int(request.query_params.get('days', 90))
            analyzer = PaymentPatternAnalyzer(request.user.company.id)
            
            # Analyze patterns first
            analyzer.analyze_payment_patterns()
            analyzer.analyze_fixed_expenses()
            
            # Get predictions
            predictions = analyzer.predict_future_payments(days)
            
            return Response({
                'status': 'success',
                'data': {
                    'predictions': predictions,
                    'company': request.user.company.name,
                    'days': days,
                    'dataPoints': {
                        'patterns': len(analyzer.payment_patterns),
                        'fixed_expenses': len(analyzer.fixed_expenses)
                    }
                }
            })
            
        except ValueError as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=500)