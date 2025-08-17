from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
import logging
from .models import Company
from transactions.models import PaymentPattern, FixedExpense, TallyTransaction
from django.db.models import Avg
import time
from .payment_analysis import PaymentPatternAnalyzer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def model_status(request):
    """Check if the AI model is trained and ready"""
    try:
        company_id = request.GET.get('company_id')
        if not company_id:
            # If no company_id provided, try to get it from the user's profile
            if hasattr(request.user, 'company_id'):
                company_id = request.user.company_id
            else:
                return Response({
                    'status': 'error',
                    'message': 'Company ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Check if we have raw transaction data
        has_transactions = TallyTransaction.objects.filter(company_id=company_id).exists()
        if not has_transactions:
            return Response({
                'status': 'success',
                'data': {
                    'isReady': False,
                    'message': 'No transaction data found. Please sync data from Tally first.',
                    'details': {
                        'has_transactions': False,
                        'patterns_available': False,
                        'expenses_available': False
                    }
                }
            })

        # Check for essential transaction types
        has_sales = TallyTransaction.objects.filter(
            company_id=company_id,
            register_type='sales'
        ).exists()
        has_receipts = TallyTransaction.objects.filter(
            company_id=company_id,
            register_type='receipt'
        ).exists()
        has_patterns = PaymentPattern.objects.filter(company_id=company_id).exists()
        has_expenses = FixedExpense.objects.filter(company_id=company_id).exists()

        # System is ready if we have all required data
        is_ready = all([has_transactions, has_sales, has_receipts, has_patterns, has_expenses])

        return Response({
            'status': 'success',
            'data': {
                'isReady': is_ready,
                'message': None if is_ready else 'Model training required.',
                'details': {
                    'has_transactions': has_transactions,
                    'has_sales': has_sales,
                    'has_receipts': has_receipts,
                    'patterns_available': has_patterns,
                    'expenses_available': has_expenses
                }
            }
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def train_model(request):
    """Train the model for a specific company"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)  # Enable debug logging
    
    def log_progress(step, message, progress=0, total=0, status='processing'):
        logger.info(f"Training progress - Step: {step}, Status: {status}, Progress: {progress}/{total} - {message}")
        
    try:
        # Debug: log incoming Authorization header to help diagnose 401s from the mobile client
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        logger.debug(f"Incoming Authorization header: {auth_header}")

        if request.method == 'GET':
            # Return current training status
            company_id = request.GET.get('company_id') or request.user.company_id
            has_patterns = PaymentPattern.objects.filter(company_id=company_id).exists()
            has_expenses = FixedExpense.objects.filter(company_id=company_id).exists()
            return Response({
                'status': 'success',
                'data': {
                    'status': 'trained' if (has_patterns and has_expenses) else 'untrained',
                    'patterns_available': has_patterns,
                    'expenses_available': has_expenses
                }
            })
        
        # POST method handling
        company_id = request.data.get('company_id') or request.user.company_id
        step = request.data.get('step')
        
        if not company_id or not step:
            return Response({
                'status': 'error',
                'message': 'Company ID and step are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if step == 'data-loading':
            from transactions.data_processor import normalize_transactions
            from .party_analysis import PartyBalanceManager
            try:
                # Step 1: Check for raw data
                raw_count = TallyTransaction.objects.filter(company_id=company_id).count()
                if raw_count == 0:
                    return Response({
                        'status': 'error',
                        'message': 'No Tally data found. Please sync data from Tally first.',
                        'details': {
                            'error_type': 'NO_DATA',
                            'help': 'Use the Desktop_tally_sync-agent to import data from Tally.'
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                log_progress('data-loading', 'Starting data normalization', 0, raw_count)
                
                # Step 2: Process raw data
                processed_count = normalize_transactions(company_id)
                log_progress('data-loading', 'Data normalization complete', processed_count, raw_count)
                
                # Step 3: Generate party balances
                generated, updated = PartyBalanceManager.generate_party_balances(company_id)
                log_progress('data-loading', 'Party balances generated', 
                           progress=100, total=100,
                           status='complete')
                
                # Cache the progress
                cache_key = f'model_training_progress_{company_id}'
                cache.set(cache_key, {
                    'step': 'data-loading',
                    'completed': True,
                    'processed_transactions': processed_count,
                    'party_balances': generated + updated
                }, timeout=3600)  # Cache for 1 hour
                
                return Response({
                    'status': 'success',
                    'data': {
                        'progress': 100,
                        'raw_count': raw_count,
                        'processed_count': processed_count,
                        'party_balances': {
                            'generated': generated,
                            'updated': updated
                        },
                        'message': f'Data processing complete: {processed_count} transactions normalized, {generated} party balances created, {updated} updated'
                    }
                })
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                logger.error(f"Training error in data-loading step: {str(e)}\n{error_detail}")
                log_progress('data-loading', f'Error: {str(e)}', status='error')
                return Response({
                    'status': 'error',
                    'message': f'Error processing transactions: {str(e)}',
                    'details': {
                        'error_type': 'PROCESSING_ERROR',
                        'error_detail': error_detail,
                        'raw_count': raw_count if 'raw_count' in locals() else 0
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif step == 'payment-patterns':
            # Use the enhanced PaymentPatternAnalyzer
            try:
                log_progress('payment-patterns', 'Starting payment pattern analysis', 0, 100)
                
                # Step 1: Verify data prerequisites
                total_transactions = TallyTransaction.objects.filter(company_id=company_id).count()
                if total_transactions == 0:
                    log_progress('payment-patterns', 'No transaction data found', status='error')
                    return Response({
                        'status': 'error',
                        'message': 'No transaction data found. Please import your Tally data first using the desktop sync agent or manual import.',
                        'details': {
                            'error_type': 'NO_DATA',
                            'help': 'Use the Desktop_tally_sync-agent to import your Tally data.'
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Check for sales and receipts specifically
                sales_count = TallyTransaction.objects.filter(
                    company_id=company_id,
                    register_type='sales'
                ).count()
                receipts_count = TallyTransaction.objects.filter(
                    company_id=company_id,
                    register_type='receipt'
                ).count()
                
                if sales_count == 0:
                    return Response({
                        'status': 'error',
                        'message': 'No sales transactions found. Please ensure your Tally data includes sales transactions.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if receipts_count == 0:
                    return Response({
                        'status': 'error',
                        'message': 'No receipt transactions found. Please ensure your Tally data includes receipt transactions.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                log_progress('payment-patterns', 'Initializing pattern analyzer', 20, 100)
                analyzer = PaymentPatternAnalyzer(company_id)
                
                log_progress('payment-patterns', 'Analyzing payment patterns', 40, 100)
                patterns = analyzer.analyze_payment_patterns()
                
                # Check if we have any patterns
                if not patterns:
                    log_progress('payment-patterns', 'No patterns found', status='error')
                    return Response({
                        'status': 'error',
                        'message': 'Failed to analyze payment patterns. Please ensure you have valid transaction data with matching sales and receipts.',
                        'details': {
                            'error_type': 'NO_PATTERNS',
                            'total_transactions': total_transactions,
                            'sales_count': sales_count,
                            'receipts_count': receipts_count
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Cache the results
                cache_key = f'model_training_progress_{company_id}'
                cache.set(cache_key, {
                    'step': 'payment-patterns',
                    'completed': True,
                    'pattern_count': len(patterns)
                }, timeout=3600)  # Cache for 1 hour
                
                log_progress('payment-patterns', f'Analysis complete: {len(patterns)} patterns found', 
                           progress=100, total=100, 
                           status='complete')
                
                return Response({
                    'status': 'success',
                    'data': {
                        'progress': 100,
                        'count': len(patterns),
                        'total_transactions': total_transactions,
                        'sales_count': sales_count,
                        'receipts_count': receipts_count,
                        'message': f'Payment patterns analyzed for {len(patterns)} parties'
                    }
                })
            except Exception as e:
                logger.error(f"Error in payment-patterns step: {str(e)}")
                log_progress('payment-patterns', f'Error: {str(e)}', status='error')
                return Response({
                    'status': 'error',
                    'message': f'Failed to analyze payment patterns: {str(e)}',
                    'details': {
                        'error_type': 'ANALYSIS_ERROR',
                        'total_transactions': total_transactions if 'total_transactions' in locals() else 0
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif step == 'fixed-expenses':
            # Process fixed expenses using the analyzer
            try:
                log_progress('fixed-expenses', 'Starting fixed expenses analysis', 0, 100)
                
                # Step 1: Verify payment patterns exist
                pattern_count = PaymentPattern.objects.filter(company_id=company_id).count()
                if pattern_count == 0:
                    log_progress('fixed-expenses', 'No payment patterns found', status='error')
                    return Response({
                        'status': 'error',
                        'message': 'No payment patterns found. Please complete the payment pattern analysis first.',
                        'details': {
                            'error_type': 'NO_PATTERNS',
                            'help': 'Run the payment-patterns step before analyzing fixed expenses.'
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                log_progress('fixed-expenses', 'Initializing expense analyzer', 20, 100)
                analyzer = PaymentPatternAnalyzer(company_id)
                
                log_progress('fixed-expenses', 'Analyzing fixed expenses', 40, 100)
                expenses = analyzer.analyze_fixed_expenses()
                
                # Cache the results
                cache_key = f'model_training_progress_{company_id}'
                cache.set(cache_key, {
                    'step': 'fixed-expenses',
                    'completed': True,
                    'expense_count': len(expenses)
                }, timeout=3600)  # Cache for 1 hour
                
                log_progress('fixed-expenses', f'Analysis complete: {len(expenses)} fixed expenses found', 
                           progress=100, total=100, 
                           status='complete')
                
                return Response({
                    'status': 'success',
                    'data': {
                        'progress': 100,
                        'count': len(expenses),
                        'pattern_count': pattern_count,
                        'message': f'Fixed expenses processed: {len(expenses)} found'
                    }
                })
            except Exception as e:
                logger.error(f"Error in fixed-expenses step: {str(e)}")
                log_progress('fixed-expenses', f'Error: {str(e)}', status='error')
                return Response({
                    'status': 'error',
                    'message': f'Failed to process fixed expenses: {str(e)}',
                    'details': {
                        'error_type': 'ANALYSIS_ERROR',
                        'pattern_count': pattern_count if 'pattern_count' in locals() else 0
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif step == 'cashflow-setup':
            # Setup cashflow predictions
            try:
                log_progress('cashflow-setup', 'Starting cashflow setup', 0, 100)
                
                # Step 1: Verify prerequisites
                pattern_count = PaymentPattern.objects.filter(company_id=company_id).count()
                expense_count = FixedExpense.objects.filter(company_id=company_id).count()
                
                if pattern_count == 0 or expense_count == 0:
                    log_progress('cashflow-setup', 'Missing required data', status='error')
                    return Response({
                        'status': 'error',
                        'message': 'Missing required data for cashflow predictions.',
                        'details': {
                            'error_type': 'INCOMPLETE_DATA',
                            'help': 'Complete both payment pattern and fixed expense analysis first.',
                            'pattern_count': pattern_count,
                            'expense_count': expense_count
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                log_progress('cashflow-setup', 'Initializing cashflow analyzer', 20, 100)
                analyzer = PaymentPatternAnalyzer(company_id)
                
                log_progress('cashflow-setup', 'Setting up cashflow predictions', 40, 100)
                current_balance = analyzer.get_current_bank_balance()
                
                # Cache the results
                cache_key = f'model_training_progress_{company_id}'
                cache.set(cache_key, {
                    'step': 'cashflow-setup',
                    'completed': True,
                    'balance': current_balance
                }, timeout=3600)  # Cache for 1 hour
                
                log_progress('cashflow-setup', 'Cashflow setup complete', 
                           progress=100, total=100, 
                           status='complete')
                
                return Response({
                    'status': 'success',
                    'data': {
                        'progress': 100,
                        'pattern_count': pattern_count,
                        'expense_count': expense_count,
                        'current_balance': current_balance,
                        'message': 'Cashflow predictions setup complete'
                    }
                })
            except Exception as e:
                logger.error(f"Error in cashflow-setup step: {str(e)}")
                log_progress('cashflow-setup', f'Error: {str(e)}', status='error')
                return Response({
                    'status': 'error',
                    'message': f'Failed to setup cashflow predictions: {str(e)}',
                    'details': {
                        'error_type': 'SETUP_ERROR',
                        'pattern_count': pattern_count if 'pattern_count' in locals() else 0,
                        'expense_count': expense_count if 'expense_count' in locals() else 0
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        else:
            return Response({
                'status': 'error',
                'message': 'Invalid training step'
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def analyze_payment_patterns(company_id):
    """Analyze payment patterns for a company using the enhanced analyzer"""
    try:
        analyzer = PaymentPatternAnalyzer(company_id)
        patterns = analyzer.analyze_payment_patterns()
        return patterns
    except Exception as e:
        print(f"Error in analyze_payment_patterns: {str(e)}")
        return []

def process_fixed_expenses(company_id):
    """Process and identify fixed expenses using the enhanced analyzer"""
    try:
        analyzer = PaymentPatternAnalyzer(company_id)
        expenses = analyzer.analyze_fixed_expenses()
        return expenses
    except Exception as e:
        print(f"Error in process_fixed_expenses: {str(e)}")
        return []

def setup_cashflow_predictions(company_id):
    """Setup initial cashflow predictions"""
    try:
        analyzer = PaymentPatternAnalyzer(company_id)
        # Initialize cashflow prediction system
        analyzer.get_current_bank_balance()
        return True
    except Exception as e:
        print(f"Error in setup_cashflow_predictions: {str(e)}")
        return False

def calculate_confidence_score(transactions):
    """Calculate confidence score based on transaction consistency"""
    if not transactions:
        return 0.5
    
    # Simple confidence calculation based on number of transactions
    # More transactions = higher confidence, up to 0.95
    count = transactions.count()
    return min(0.5 + (count * 0.05), 0.95)
