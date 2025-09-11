from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.utils import timezone
from accounts.models import Company
from transactions.models import (
    TallyTransaction, PaymentPattern,
    FixedExpense, PartyBalance
)
from .data_pipeline import DataPipeline
from accounts.payment_analysis import PaymentPatternAnalyzer
import logging

logger = logging.getLogger(__name__)

class ModelTrainingViewSet(viewsets.ViewSet):
    """
    ViewSet for model training and data processing operations with fallback
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def _check_existing_data(self, company_id):
        """Check if company has existing patterns and predictions"""
        pattern_count = PaymentPattern.objects.filter(company_id=company_id).count()
        expense_count = FixedExpense.objects.filter(company_id=company_id).count()
        balance_count = PartyBalance.objects.filter(company_id=company_id).count()
        
        return {
            'has_patterns': pattern_count > 0,
            'has_expenses': expense_count > 0,
            'has_balances': balance_count > 0,
            'metrics': {
                'patterns': pattern_count,
                'expenses': expense_count,
                'balances': balance_count
            }
        }
    
    @action(detail=True, methods=['post'])
    def process_company_data(self, request, pk=None):
        """
        Transform raw Tally data into processed transaction models
        with fallback to existing data if no new data is available
        """
        try:
            company = Company.objects.get(pk=pk)
            
            # First check if we have existing patterns/predictions
            existing_data = self._check_existing_data(company.id)
            if all([
                existing_data['has_patterns'],
                existing_data['has_expenses'],
                existing_data['has_balances']
            ]):
                # If we have existing data, return success with metrics
                return Response({
                    'status': 'success',
                    'message': 'Using existing predictions - no new data to process',
                    'metrics': existing_data['metrics']
                })
            
            # Check for new raw data
            tally_count = TallyTransaction.objects.filter(company_id=company.id).count()
            valid_transactions = TallyTransaction.objects.filter(
                company_id=company.id,
                amount__gt=0
            ).count()
            
            # If no raw data but we have some existing predictions, use those
            if tally_count == 0 and any([
                existing_data['has_patterns'],
                existing_data['has_expenses'],
                existing_data['has_balances']
            ]):
                return Response({
                    'status': 'success',
                    'message': 'Using existing predictions - no new raw data available',
                    'metrics': existing_data['metrics']
                })
            
            # No raw data and no existing predictions
            if tally_count == 0:
                return Response({
                    'status': 'error',
                    'message': 'No Tally data found. Please sync data from Tally first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if valid_transactions == 0:
                return Response({
                    'status': 'error',
                    'message': 'No valid transaction data found. Please check your Tally sync.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Found {tally_count} raw transactions ({valid_transactions} valid) for company {company.id}")
            
            # Process raw data into transaction models
            pipeline = DataPipeline(company.id)
            try:
                result = pipeline.process_tally_data()
                logger.info(f"Pipeline processing result: {result}")
                
                if result['status'] != 'success':
                    # If processing fails but we have existing data, use that
                    if any([
                        existing_data['has_patterns'],
                        existing_data['has_expenses'],
                        existing_data['has_balances']
                    ]):
                        return Response({
                            'status': 'success',
                            'message': 'Using existing predictions - new data processing failed',
                            'metrics': existing_data['metrics']
                        })
                    
                    logger.error(f"Pipeline processing failed: {result}")
                    return Response({
                        'status': 'error',
                        'message': result.get('message', 'Data processing failed')
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                if not result.get('metrics', {}).get('normalized_transactions', 0):
                    # If normalization produces no results but we have existing data, use that
                    if any([
                        existing_data['has_patterns'],
                        existing_data['has_expenses'],
                        existing_data['has_balances']
                    ]):
                        return Response({
                            'status': 'success',
                            'message': 'Using existing predictions - no new transactions normalized',
                            'metrics': existing_data['metrics']
                        })
                    
                    logger.warning("No transactions were normalized during processing")
                    return Response({
                        'status': 'error',
                        'message': 'No transaction data was processed. Please check your Tally import.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                # If processing errors but we have existing data, use that
                if any([
                    existing_data['has_patterns'],
                    existing_data['has_expenses'],
                    existing_data['has_balances']
                ]):
                    return Response({
                        'status': 'success',
                        'message': 'Using existing predictions - error processing new data',
                        'metrics': existing_data['metrics']
                    })
                
                logger.error(f"Pipeline processing error: {str(e)}", exc_info=True)
                return Response({
                    'status': 'error',
                    'message': f"Error processing data: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Generate patterns and analyze data
            try:
                logger.info("Generating payment patterns and analyzing data...")
                analyzer = PaymentPatternAnalyzer(company.id)
                
                # Generate payment patterns
                patterns = analyzer.analyze_payment_patterns()
                logger.info(f"Generated {len(patterns)} payment patterns")
                
                # Extract fixed expenses
                expenses = analyzer.analyze_fixed_expenses()
                logger.info(f"Identified {len(expenses)} fixed expenses")
                
                # Update party balances with predictions
                balances = analyzer.calculate_party_balances()
                logger.info(f"Updated balances for {len(balances)} parties")
                
                # Update company metadata
                company.last_data_processing = timezone.now()
                company.is_data_processed = True
                company.save()
                
                return Response({
                    'status': 'success',
                    'message': 'Data processing and analysis completed successfully',
                    'metrics': {
                        **result['metrics'],
                        'payment_patterns': len(patterns),
                        'fixed_expenses': len(expenses),
                        'party_balances': len(balances)
                    }
                })
                
            except Exception as analysis_error:
                # If analysis fails but we have existing data, use that
                if any([
                    existing_data['has_patterns'],
                    existing_data['has_expenses'],
                    existing_data['has_balances']
                ]):
                    return Response({
                        'status': 'success',
                        'message': 'Using existing predictions - error analyzing new data',
                        'metrics': existing_data['metrics']
                    })
                
                logger.error(f"Analysis error: {str(analysis_error)}")
                return Response({
                    'status': 'error',
                    'message': f"Error during data analysis: {str(analysis_error)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Company.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Company not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            # Final fallback - if we have any existing data, use it
            existing_data = self._check_existing_data(pk)
            if any([
                existing_data['has_patterns'],
                existing_data['has_expenses'],
                existing_data['has_balances']
            ]):
                return Response({
                    'status': 'success', 
                    'message': 'Using existing predictions - unexpected error with new data',
                    'metrics': existing_data['metrics']
                })
            
            logger.error(f"Error processing company data: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
