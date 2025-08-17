from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.db import transaction
from .exceptions import APIException
from .payment_analysis_improved import PaymentPatternAnalyzer
import logging

logger = logging.getLogger(__name__)

class PaymentAnalysisView(APIView):
    def get(self, request, company_id=None):
        try:
            # Get company_id from URL params or query params
            company_id = company_id or request.GET.get('company_id')
            if not company_id:
                return Response({
                    'status': 'error',
                    'message': "company_id is required",
                    'party_statistics': {},
                    'aging_analysis': {},
                    'payment_trends': {},
                    'total_parties': 0,
                    'total_patterns': 0,
                    'data_available': False
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Cache key for this company's analysis
            cache_key = f'payment_analysis_{company_id}'
            
            # Try to get cached analysis
            cached_analysis = cache.get(cache_key)
            if cached_analysis:
                return Response(cached_analysis)
            
            # If no cached data, perform analysis
            with transaction.atomic():
                analyzer = PaymentPatternAnalyzer(company_id)
                analysis = analyzer.get_payment_analysis()
                
                # Cache the results for 15 minutes to reduce recomputations
                cache.set(cache_key, analysis, 900)
                
                # Ensure all required fields are present
                response_data = {
                    'status': 'success',
                    'party_statistics': analysis.get('party_statistics', {}),
                    'aging_analysis': analysis.get('aging_analysis', {}),
                    'payment_trends': analysis.get('payment_trends', {}),
                    'total_parties': analysis.get('total_parties', 0),
                    'total_patterns': analysis.get('total_patterns', 0),
                    'data_available': True
                }
                return Response(response_data)
                
        except Exception as e:
            logger.error(f"Error in payment analysis for company {company_id}: {str(e)}")
            return Response({
                'status': 'error',
                'message': f"Failed to fetch payment analysis: {str(e)}",
                'party_statistics': {},
                'aging_analysis': {},
                'payment_trends': {},
                'total_parties': 0,
                'total_patterns': 0,
                'data_available': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UnpaidSalesView(APIView):
    def get(self, request, company_id=None):
        try:
            # Get company_id from URL params or query params
            company_id = company_id or request.GET.get('company_id')
            if not company_id:
                raise APIException(
                    message="company_id is required",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
            logger.debug(f"Fetching unpaid sales for company {company_id}")
            # Cache key for unpaid sales
            cache_key = f'unpaid_sales_{company_id}'
            
            # Try to get cached data
            cached_sales = cache.get(cache_key)
            if cached_sales:
                logger.debug(f"Returning cached unpaid sales for company {company_id}")
                response_data = {
                    'status': 'success',
                    'data': {
                        'unpaid_sales': cached_sales.get('unpaid_sales', []),
                        'total_unpaid': cached_sales.get('total_unpaid', 0),
                        'count': cached_sales.get('count', 0),
                        'data_available': True
                    }
                }
                return Response(response_data)
            
            # If no cached data, fetch unpaid sales
            with transaction.atomic():
                analyzer = PaymentPatternAnalyzer(company_id)
                unpaid_sales = analyzer.get_unpaid_sales()
                
                # Cache the results for 15 minutes to reduce recomputations
                cache.set(cache_key, unpaid_sales, 900)
                
                response_data = {
                    'status': 'success',
                    'data': {
                        'unpaid_sales': unpaid_sales.get('unpaid_sales', []),
                        'total_unpaid': unpaid_sales.get('total_unpaid', 0),
                        'count': unpaid_sales.get('count', 0),
                        'data_available': True
                    }
                }
                return Response(response_data)
                
        except Exception as e:
            logger.error(f"Error fetching unpaid sales for company {company_id}: {str(e)}")
            return Response({
                'status': 'error',
                'message': f"Failed to fetch unpaid sales: {str(e)}",
                'data': {
                    'unpaid_sales': [],
                    'total_unpaid': 0,
                    'count': 0,
                    'data_available': False
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
