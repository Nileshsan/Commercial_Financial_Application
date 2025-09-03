from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .payment_analysis import PaymentPatternAnalyzer
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def train_model(request):
    """Train model based on transaction data"""
    try:
        company_id = request.user.company_id
        step = request.data.get('step', 'all')
        
        if step == 'data-loading':
            # Just validate that we have transaction data
            from .models import TallyTransaction
            count = TallyTransaction.objects.filter(company_id=company_id).count()
            if count == 0:
                return Response({
                    'status': 'error',
                    'message': 'No transaction data found. Please sync data first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'status': 'success',
                'data': {
                    'count': count,
                    'message': 'Data loaded successfully',
                    'progress': 100
                }
            })
            
        elif step == 'payment-patterns':
            # Analyze payment patterns
            analyzer = PaymentPatternAnalyzer(company_id)
            patterns = analyzer.analyze_payment_patterns()
            
            if patterns is None:
                # Get transaction stats for better error message
                from .models import TallyTransaction
                sales_count = TallyTransaction.objects.filter(company_id=company_id, register_type='sales').count()
                receipt_count = TallyTransaction.objects.filter(company_id=company_id, register_type='receipt').count()
                
                logger.error(f"Payment pattern analysis failed for company {company_id}. "
                           f"Found {sales_count} sales and {receipt_count} receipts.")
                
                # Get party stats
                sales_parties = set(TallyTransaction.objects.filter(
                    company_id=company_id, 
                    register_type='sales'
                ).values_list('party_name', flat=True).distinct())
                
                receipt_parties = set(TallyTransaction.objects.filter(
                    company_id=company_id, 
                    register_type='receipt'
                ).values_list('party_name', flat=True).distinct())
                
                matching_parties = sales_parties.intersection(receipt_parties)
                
                return Response({
                    'status': 'error',
                    'message': 'Failed to analyze payment patterns.\n\n'
                              f'• Found {sales_count} sales and {receipt_count} receipts\n'
                              f'• {len(sales_parties)} parties have sales\n'
                              f'• {len(receipt_parties)} parties have receipts\n'
                              f'• Only {len(matching_parties)} parties have both\n\n'
                              'Action needed: Please ensure each party has matching sales and receipts.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not patterns:
                logger.warning(f"No payment patterns found for company {company_id}")
                return Response({
                    'status': 'error',
                    'message': 'No payment patterns could be found. This usually means there are no parties '
                              'that have both sales and receipt transactions, or the party names do not match exactly. '
                              'Please check your transaction data for consistency.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'status': 'success',
                'data': {
                    'patterns': len(patterns),
                    'message': 'Payment patterns analyzed successfully',
                    'progress': 100
                }
            })
            
        elif step == 'all':
            # Run complete training process
            analyzer = PaymentPatternAnalyzer(company_id)
            patterns = analyzer.analyze_payment_patterns()
            
            if patterns is None:
                # Log specific error message from payment analysis
                logger.error(f"Payment pattern analysis failed or returned no patterns for company {company_id}")
                return Response({
                    'status': 'error',
                    'message': 'Failed to analyze payment patterns. Please ensure you have valid transaction data with matching sales and receipts from the same parties.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not patterns:
                logger.warning(f"No payment patterns found for company {company_id}")
                return Response({
                    'status': 'error',
                    'message': 'No payment patterns could be found. Please ensure you have both sales and receipt transactions for the same parties.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'status': 'success',
                'data': {
                    'patterns': len(patterns),
                    'message': 'Model training completed successfully',
                    'progress': 100
                }
            })
            
    except Exception as e:
        logger.error(f"Error in model training: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
