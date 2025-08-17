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
    ViewSet for model training and data processing operations
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def process_company_data(self, request, pk=None):
        """
        Transform raw Tally data into processed transaction models
        Steps:
        1. Verify raw data exists
        2. Process into transaction models
        3. Generate patterns and predictions
        """
        try:
            company = Company.objects.get(pk=pk)
            
            # Step 1: Verify raw data exists and is valid
            tally_count = TallyTransaction.objects.filter(company_id=company.id).count()
            if tally_count == 0:
                return Response({
                    'status': 'error',
                    'message': 'No Tally data found. Please sync data from Tally first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if we have valid transaction data
            valid_transactions = TallyTransaction.objects.filter(
                company_id=company.id,
                amount__gt=0
            ).count()
            
            if valid_transactions == 0:
                return Response({
                    'status': 'error',
                    'message': 'No valid transaction data found. Please check your Tally sync.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Found {tally_count} raw transactions ({valid_transactions} valid) for company {company.id}")
            
            # Step 2: Process raw data into transaction models
            pipeline = DataPipeline(company.id)
            try:
                result = pipeline.process_tally_data()
                logger.info(f"Pipeline processing result: {result}")
                
                if result['status'] != 'success':
                    logger.error(f"Pipeline processing failed: {result}")
                    return Response({
                        'status': 'error',
                        'message': result.get('message', 'Data processing failed')
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                if not result.get('metrics', {}).get('normalized_transactions', 0):
                    logger.warning("No transactions were normalized during processing")
                    return Response({
                        'status': 'error',
                        'message': 'No transaction data was processed. Please check your Tally import.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Pipeline processing error: {str(e)}", exc_info=True)
                return Response({
                    'status': 'error',
                    'message': f"Error processing data: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Step 3: Generate patterns and analyze data
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
            logger.error(f"Error processing company data: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def processing_status(self, request, pk=None):
        """
        Get detailed processing status and data readiness metrics for a company
        """
        try:
            company = Company.objects.get(pk=pk)
            
            # Get counts of raw and processed data
            tally_count = TallyTransaction.objects.filter(company_id=company.id).count()
            pattern_count = PaymentPattern.objects.filter(company_id=company.id).count()
            expense_count = FixedExpense.objects.filter(company_id=company.id).count()
            balance_count = PartyBalance.objects.filter(company_id=company.id).count()
            
            return Response({
                'status': 'success',
                'data': {
                    'is_processed': company.is_data_processed,
                    'last_processing': company.last_data_processing,
                    'company_name': company.name,
                    'metrics': {
                        'raw_data': {
                            'tally_transactions': tally_count
                        },
                        'processed_data': {
                            'payment_patterns': pattern_count,
                            'fixed_expenses': expense_count,
                            'party_balances': balance_count
                        },
                        'data_readiness': {
                            'has_raw_data': tally_count > 0,
                            'has_patterns': pattern_count > 0,
                            'has_expenses': expense_count > 0,
                            'has_balances': balance_count > 0,
                            'is_ready_for_predictions': all([
                                tally_count > 0,
                                pattern_count > 0,
                                balance_count > 0
                            ])
                        }
                    }
                }
            })
        except Company.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Company not found'
            }, status=status.HTTP_404_NOT_FOUND)
