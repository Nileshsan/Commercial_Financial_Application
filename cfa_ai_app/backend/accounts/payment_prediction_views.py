from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.db.models import Sum
from django.core.cache import cache
from .payment_analysis import PaymentPatternAnalyzer
from .party_analysis import PartyBalanceManager
from transactions.models import (
    TallyTransaction, LedgerMaster, BankBalance, 
    PaymentPattern, FixedExpense, PartyBalance
)
from .models import LedgerOpeningBalance
from datetime import datetime, timedelta
import pandas as pd
from decimal import Decimal
import logging

# Configure decimal precision
from decimal import getcontext
getcontext().prec = 10  # Set decimal precision to handle currency calculations

logger = logging.getLogger(__name__)

def log_error(e, context=""):
    """
    Centralized error logging with context
    """
    logger.error(f"{context} - Error: {str(e)}")
    if hasattr(e, '__traceback__'):
        import traceback
        logger.error(traceback.format_exc())
    return str(e)

def validate_company_id(company_id):
    """
    Validate company_id and ensure required data exists
    """
    if not company_id:
        raise ValueError("company_id parameter is required")
    
    try:
        # Check TallyTransaction data
        tally_count = TallyTransaction.objects.filter(company_id=company_id).count()
        sales_count = TallyTransaction.objects.filter(
            company_id=company_id, 
            register_type='sales'
        ).count()
        receipt_count = TallyTransaction.objects.filter(
            company_id=company_id, 
            register_type='receipt'
        ).count()
        
        missing_data = []
        if tally_count == 0:
            missing_data.append("No Tally transactions found")
        else:
            if sales_count == 0:
                missing_data.append("No sales transactions found")
            if receipt_count == 0:
                missing_data.append("No receipt transactions found")
        
        # Check and potentially update party balances
        balances_exist, needs_update, balance_message = PartyBalanceManager.validate_party_balances(company_id)
        if not balances_exist or needs_update:
            try:
                generated, updated = PartyBalanceManager.generate_party_balances(company_id)
                logger.info(f"Generated {generated} and updated {updated} party balances")
            except Exception as e:
                missing_data.append(f"Error generating party balances: {str(e)}")
        
        # Check if fixed expenses exist
        fixed_expenses_count = FixedExpense.objects.filter(
            company_id=company_id,
            is_active=True
        ).count()
        if fixed_expenses_count == 0:
            missing_data.append("No active fixed expenses found")
            
        if missing_data:
            error_msg = (
                f"Data missing for company_id {company_id}:\\n" + 
                "\\n".join(f"- {msg}" for msg in missing_data) + 
                "\\n\\nPlease import your Tally data first using the desktop sync agent or manual import. " +
                "You can find the Tally sync agent in the Desktop_tally_sync-agent folder."
            )
            raise ValueError(error_msg)
            
        return {
            'tally_transactions': tally_count,
            'sales_transactions': sales_count,
            'receipt_transactions': receipt_count,
            'party_balances': PartyBalance.objects.filter(company_id=company_id).count(),
            'fixed_expenses': fixed_expenses_count
        }
        
    except Exception as e:
        logger.error(f"Error validating company_id {company_id}: {str(e)}")
        if "Data missing for company_id" in str(e):
            raise ValueError(str(e))
        raise ValueError(f"Error accessing company data: {str(e)}")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_party_payment_behavior(request, party_name):
    """
    Analyze payment behavior for a specific party
    """
    try:
        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response({
                'status': 'error',
                'message': 'company_id parameter is required'
            }, status=400)
            
        analyzer = PaymentPatternAnalyzer(company_id)
        analyzer.analyze_payment_patterns()  # This updates payment patterns
        pattern = analyzer.payment_patterns.get(party_name, {})
        
        return Response({
            'status': 'success',
            'data': {
                'party_name': party_name,
                'avg_payment_days': pattern.get('avg_delay', 0),
                'confidence': pattern.get('confidence', 0),
                'sample_size': pattern.get('sample_size', 0),
                'std_deviation': pattern.get('std_deviation', 0)
            }
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_bank_balance(request):
    """
    GET: Retrieve current bank balance
    POST: Update bank balance
    """
    try:
        company_id = request.query_params.get('company_id') or request.data.get('company_id')
        account_name = request.query_params.get('account_name', 'default')
        
        if not company_id:
            return Response({
                'status': 'error',
                'message': 'company_id parameter is required'
            }, status=400)
            
        # Log the operation
        logger.info(f"Managing bank balance for company {company_id}, account {account_name}, method {request.method}")

        # Get or create bank balance record
        bank_balance, created = BankBalance.objects.get_or_create(
            company_id=company_id,
            account_name=account_name,
            defaults={'balance': Decimal('0.00')}
        )

        if request.method == 'GET':
            return Response({
                'status': 'success',
                'data': {
                    'balance': float(bank_balance.balance),
                    'updated_at': bank_balance.updated_at.isoformat() if bank_balance.updated_at else None
                }
            })
        else:  # POST
            try:
                new_balance = Decimal(str(request.data.get('balance')))
                bank_balance.balance = new_balance
                bank_balance.updated_at = timezone.now()
                bank_balance.save()
                
                return Response({
                    'status': 'success',
                    'data': {
                        'balance': float(bank_balance.balance),
                        'updated_at': bank_balance.updated_at.isoformat()
                    }
                })
            except (TypeError, ValueError):
                return Response({
                    'status': 'error',
                    'message': 'Invalid balance value provided'
                }, status=400)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)

from django.core.cache import cache
from django.conf import settings
from datetime import date

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_data_status(request):
    """
    Check the status of all required data for predictions
    """
    company_id = request.query_params.get('company_id')
    if not company_id:
        return Response({
            'status': 'error',
            'message': 'company_id parameter is required'
        }, status=400)
        
    try:
        # Check all required data
        data_status = {
            'tally_transactions': {
                'total': TallyTransaction.objects.filter(company_id=company_id).count(),
                'sales': TallyTransaction.objects.filter(company_id=company_id, register_type='sales').count(),
                'receipts': TallyTransaction.objects.filter(company_id=company_id, register_type='receipt').count(),
                'latest_transaction': TallyTransaction.objects.filter(company_id=company_id).order_by('-date').values('date').first()
            },
            'ledger_balances': {
                'total': LedgerOpeningBalance.objects.filter(company_id=company_id).count(),
                'latest': LedgerOpeningBalance.objects.filter(company_id=company_id).order_by('-id').values('ledger_name').first()
            },
            'party_balances': {
                'total': PartyBalance.objects.filter(company_id=company_id).count(),
                'latest': PartyBalance.objects.filter(company_id=company_id).order_by('-id').values('party_name', 'current_balance').first()
            },
            'fixed_expenses': {
                'total': FixedExpense.objects.filter(company_id=company_id, is_active=True).count(),
                'latest': FixedExpense.objects.filter(company_id=company_id, is_active=True).values('description', 'amount').first()
            }
        }
        
        # Add recommendations
        recommendations = []
        if data_status['tally_transactions']['total'] == 0:
            recommendations.append("Run the Tally sync agent to import transaction data")
        if data_status['ledger_balances']['total'] == 0:
            recommendations.append("Import opening balances from Tally")
        if data_status['party_balances']['total'] == 0:
            recommendations.append("Generate party balances from transaction data")
        if data_status['fixed_expenses']['total'] == 0:
            recommendations.append("Add fixed expenses in the system")
            
        return Response({
            'status': 'success',
            'data': data_status,
            'recommendations': recommendations,
            'next_steps': {
                'needs_sync': data_status['tally_transactions']['total'] == 0,
                'needs_balance_generation': data_status['party_balances']['total'] == 0 and data_status['tally_transactions']['total'] > 0,
                'ready_for_predictions': all(d['total'] > 0 for d in data_status.values())
            }
        })
        
    except Exception as e:
        logger.error(f"Error checking data status: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_predictions(request):
    """
    Get payment predictions for all parties including cashflow forecast and insights
    
    Parameters:
    - company_id: Required. The ID of the company to analyze
    - days: Optional. Number of days to predict (default: 90, max: 365)
    - include_stats: Optional. Include detailed statistics (default: false)
    - refresh_cache: Optional. Force refresh of cached data (default: false)
    """
    logger.info("Starting payment predictions request")
    
    try:
        # Get and validate input parameters
        company_id = request.query_params.get('company_id')
        if not company_id:
            return JsonResponse({
                'error': 'company_id parameter is required'
            }, status=400)
            
        try:
            days = min(int(request.query_params.get('days', 90)), 365)
        except ValueError:
            return JsonResponse({
                'error': 'Invalid days parameter'
            }, status=400)
            
        # Initialize analyzer with validation
        try:
            analyzer = PaymentPatternAnalyzer(company_id)
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            return JsonResponse({
                'error': str(ve),
                'details': 'Please ensure you have imported your Tally data'
            }, status=400)
        
        # Get predictions
        try:
            predictions = analyzer.predict_future_payments(days=days)
            if not predictions or 'data' not in predictions:
                return JsonResponse({
                    'error': 'Could not generate predictions',
                    'details': 'No valid prediction data could be generated'
                }, status=400)
                
            return JsonResponse(predictions)
            
        except Exception as e:
            logger.error(f"Error generating predictions: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': 'Error generating predictions',
                'details': str(e)
            }, status=500)
        
        logger.info(f"Processing request - Company: {company_id}, Days: {days}")
        
        # Validate company data exists
        try:
            data_status = validate_company_id(company_id)
            if not data_status['tally_transactions'] > 0:
                return JsonResponse({
                    'error': 'No transaction data found',
                    'details': 'Please import your Tally data first'
                }, status=400)
        except ValueError as ve:
            return JsonResponse({
                'error': str(ve)
            }, status=400)
            
        # Create cache key
        cache_key = f'payment_predictions_{company_id}_{days}_{date.today()}'
        
        # Check cache first if refresh not requested
        if not refresh_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached predictions for company {company_id}")
                return JsonResponse(cached_data)
                
        # Initialize analyzer and process data
        try:
            analyzer = PaymentPatternAnalyzer(company_id)
            logger.info("Analyzing payment patterns...")
            
            # Get payment patterns
            patterns = analyzer.analyze_payment_patterns()
            if not patterns:
                return JsonResponse({
                    'error': 'No payment patterns could be determined',
                    'details': 'Insufficient transaction history'
                }, status=400)
                
            logger.info(f"Found {len(patterns)} payment patterns")
            
            # Get predictions
            predictions = analyzer.predict_payment_dates()
            if not predictions:
                return JsonResponse({
                    'error': 'Could not generate predictions',
                    'details': 'No unpaid sales found'
                }, status=400)
                
            logger.info(f"Generated {len(predictions)} predictions")
            
            # Prepare response data
            response_data = {
                'status': 'success',
                'data': {
                    'patterns': patterns,
                    'predictions': predictions,
                    'metadata': {
                        'company_id': company_id,
                        'days_predicted': days,
                        'generated_at': timezone.now().isoformat()
                    }
                }
            }
            
            # Cache the results
            cache.set(cache_key, response_data, timeout=3600)  # Cache for 1 hour
            
            return JsonResponse(response_data)
            
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            return JsonResponse({
                'error': str(ve)
            }, status=400)
        except Exception as e:
            logger.error(f"Error processing predictions: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': 'Internal server error',
                'details': str(e)
            }, status=500)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': 'Internal server error',
            'details': 'An unexpected error occurred'
        }, status=500)
        logger.info("Starting main prediction processing")
        try:
            validation_result = validate_company_id(company_id)
            logger.info(f"Data validation successful: {validation_result}")
            
            # Initialize the analysis dates
            current_date = timezone.now()
            end_date = current_date + timedelta(days=days)
            logger.info(f"Analysis period: {current_date.date()} to {end_date.date()}")

        except ValueError as ve:
            logger.error(f"Data validation failed: {str(ve)}")
            return Response({
                'status': 'error',
                'message': str(ve),
                'details': {
                    'error_type': 'DATA_VALIDATION_ERROR',
                    'help': 'Please ensure you have imported your Tally data using the Desktop_tally_sync-agent.'
                }
            }, status=400)
        except Exception as e:
            logger.error(f"Error validating input parameters: {str(e)}")
            return Response({
                'status': 'error',
                'message': f"Error validating input parameters: {str(e)}"
            }, status=400)

        include_stats = request.query_params.get('include_stats', 'false').lower() == 'true'
        refresh_cache = request.query_params.get('refresh_cache', 'false').lower() == 'true'
        
        logger.info(f"Fetching predictions with: {request.query_params.dict()}")

        # Wrap entire logic in try block with detailed logging
        try:
            logger.info("Starting payment prediction process...")
            # Get data stats first
            transactions = TallyTransaction.objects.filter(company_id=company_id)
            sales_count = transactions.filter(register_type='sales').count()
            receipt_count = transactions.filter(register_type='receipt').count()
            opening_balances = LedgerOpeningBalance.objects.filter(company_id=company_id).count()
            party_balances = PartyBalance.objects.filter(company_id=company_id).count()
            
            logger.info(f"Company {company_id} data stats: Sales={sales_count}, Receipts={receipt_count}, "
                       f"Opening Balances={opening_balances}, Party Balances={party_balances}")
            
            # Then do validation
            try:
                validation_result = validate_company_id(company_id)
                logger.info(f"Company {company_id} data validation successful: {validation_result}")
            except ValueError as e:
                error_message = str(e)
                logger.error(f"Company {company_id} validation failed: {error_message}")
                return Response({
                    'status': 'error',
                    'message': error_message,
                    'details': {
                        'error_type': 'DATA_MISSING',
                        'company_id': company_id,
                        'available_data': {
                            'sales': sales_count,
                            'receipts': receipt_count,
                            'opening_balances': opening_balances,
                            'party_balances': party_balances
                        }
                    }
                }, status=400)
            
        except ValueError as e:
            error_message = str(e)
            logger.error(f"Company {company_id} validation failed: {error_message}")
            return Response({
                'status': 'error',
                'message': error_message,
                'details': {
                    'error_type': 'DATA_MISSING',
                    'company_id': company_id,
                    'available_data': {
                        'sales': sales_count if 'sales_count' in locals() else 0,
                        'receipts': receipt_count if 'receipt_count' in locals() else 0,
                        'opening_balances': opening_balances if 'opening_balances' in locals() else 0,
                        'party_balances': party_balances if 'party_balances' in locals() else 0
                    }
                }
            }, status=400)
            
        # Validate and limit the prediction days
        try:
            days = int(request.query_params.get('days', 90))
            days = min(max(1, days), 365)  # Limit between 1 and 365 days
        except ValueError:
            return Response({
                'status': 'error',
                'message': 'Invalid days parameter. Must be a number between 1 and 365.'
            }, status=400)
            
        # Check cache first if refresh not requested
        cache_key = f'payment_predictions_{company_id}_{days}_{date.today()}'
        if not refresh_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached predictions for company {company_id}")
                return Response(cached_data)
            
        days = int(request.query_params.get('days', 90))
        current_date = timezone.now()
        end_date = current_date + timedelta(days=days)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)

    try:
        # Create analyzer to get bank balance and predictions
        analyzer = PaymentPatternAnalyzer(company_id)
        
        # Get fixed expenses first
        fixed_expenses = FixedExpense.objects.filter(
            company_id=company_id,
            is_active=True
        ).values('description', 'amount', 'interval_days')
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f"Error setting up analyzer: {str(e)}"
        }, status=500)

    try:
        # Get all party balances and their transactions
        all_parties = TallyTransaction.objects.filter(
            company_id=company_id
        ).values_list('party_name', flat=True).distinct()
        
        party_transactions = {}
        current_balances = {}
        
        for party in all_parties:
            # Get all sales and receipts for this party
            sales = TallyTransaction.objects.filter(
                company_id=company_id,
                party_name=party,
                register_type='sales'
            ).order_by('date')
            
            receipts = TallyTransaction.objects.filter(
                company_id=company_id,
                party_name=party,
                register_type='receipt'
            ).order_by('date')
            
            party_transactions[party] = {
                'sales': list(sales),
                'receipts': list(receipts)
            }
    except Exception as e:
        logger.error(f"Error fetching party transactions: {str(e)}")
        return Response({
            'status': 'error',
            'message': f"Error fetching party transactions: {str(e)}"
        }, status=500)
            
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f"Error fetching transaction data: {str(e)}"
        }, status=500)

    # Calculate party transactions and current balances
    for party in all_parties:
        # Get all sales and receipts for this party
        sales = TallyTransaction.objects.filter(
            company_id=company_id,
            party_name=party,
            register_type='sales'
        ).order_by('date')
        
        receipts = TallyTransaction.objects.filter(
            company_id=company_id,
            party_name=party,
            register_type='receipt'
        ).order_by('date')
        
        # Calculate current balance including opening balance
        opening_balance = Decimal('0.00')
        try:
            from accounts.models import LedgerOpeningBalance
            opening = LedgerOpeningBalance.objects.filter(
                company_id=company_id,
                ledger_name=party
            ).first()
            if opening:
                opening_balance = opening.opening_balance
        except Exception as e:
            print(f"Error getting opening balance for {party}: {e}")
        except:
            pass
        
        # Calculate current balance
        current_balance = opening_balance
        for sale in sales:
            current_balance -= sale.amount
        for receipt in receipts:
            current_balance += receipt.amount
        
        current_balances[party] = current_balance
        party_transactions[party] = {
            'sales': list(sales),
            'receipts': list(receipts),
            'current_balance': current_balance,
            'opening_balance': opening_balance
        }
        
        try:
            # Now analyze payment patterns with FIFO matching
            payment_patterns = analyzer.analyze_payment_patterns()
            print(f"Analyzed payment patterns for {len(payment_patterns)} parties")

            # Get predictions using analyzer
            prediction_data = analyzer.predict_future_payments(days=days)
            print(f"Raw prediction data received: {prediction_data}")
            
            if not isinstance(prediction_data, dict) or 'data' not in prediction_data:
                logger.error(f"Invalid prediction data format received: {prediction_data}")
                return JsonResponse({
                    'error': 'Invalid prediction data format',
                    'details': 'The prediction engine returned an invalid response'
                }, status=500)
        except Exception as e:
            logger.error(f"Error analyzing payment patterns: {str(e)}")
            return JsonResponse({
                'error': 'Error analyzing payment patterns',
                'details': str(e)
            }, status=500)
            
        print(f"Number of prediction days: {len(prediction_data['data']['predictions'])}")
        print(f"Initial balance: {prediction_data['data']['initial_balance']}")
            
        predictions = prediction_data['data']['predictions']
        initial_balance = prediction_data['data']['initial_balance']
        
        # Start with current bank balance
        running_balance = current_balance
        formatted_predictions = []
        
        # First, predict future receipts based on current party balances
        future_receipts = []
        
        # Get all party balances first
        party_balances = PartyBalance.objects.filter(company_id=company_id)
        
        for party_balance in party_balances:
            if party_balance.current_balance < 0:  # Negative balance means they owe us money
                pattern = payment_patterns.get(party_balance.party_name, {})
                if pattern:
                    # Get latest sale for this party
                    latest_sale = TallyTransaction.objects.filter(
                        company_id=company_id,
                        party_name=party_balance.party_name,
                        register_type='sales'
                    ).order_by('-date').first()
                    
                    if latest_sale:
                        avg_delay = pattern.get('avg_delay', 30)
                        predicted_date = latest_sale.date + timedelta(days=avg_delay)
                        # Convert current_date to date object for comparison
                        if predicted_date >= current_date.date():
                            future_receipts.append({
                                'party': party_balance.party_name,
                                'amount': abs(float(party_balance.current_balance)),
                                'predicted_date': predicted_date,
                                'confidence': pattern.get('confidence', 0.5),
                                'sale_reference': latest_sale.id,
                                'avg_delay': avg_delay
                            })
        
        # Sort future receipts by date
        future_receipts.sort(key=lambda x: x['predicted_date'])
        
        # Initialize daily running balance and create prediction days
            
        # Ensure proper date handling
        if isinstance(current_date, datetime):
            current_date = current_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()

        # Generate daily predictions
        current_date_iter = current_date
        while current_date_iter <= end_date:
            daily_predictions = {
                'date': current_date_iter.strftime('%Y-%m-%d'),
                'receipts': [],
                'expenses': [],
                'running_balance': running_balance
            }
            
            # Add predicted receipts for this day
            # Convert current_date_iter to date if it's datetime
            if isinstance(current_date_iter, datetime):
                current_date_iter = current_date_iter.date()
            day_receipts = [r for r in future_receipts if r['predicted_date'] == current_date_iter]
            for receipt in day_receipts:
                receipt_amount = Decimal(str(receipt['amount']))
                daily_predictions['receipts'].append({
                    'party': receipt['party'],
                    'amount': float(receipt_amount),  # Convert to float for JSON serialization
                    'confidence': receipt['confidence'],
                    'sale_reference': receipt['sale_reference'],
                    'avg_delay': receipt['avg_delay']
                })
                running_balance = running_balance + receipt_amount  # Use explicit addition
            
            # Add fixed expenses based on their interval
            for expense in fixed_expenses:
                interval_days = expense.get('interval_days', 30)  # Default to monthly if not specified
                
                # Check if expense should be added on this date
                days_since_start = (current_date_iter - current_date.date()).days
                if days_since_start % interval_days == 0:
                    try:
                        expense_amount = Decimal(str(expense['amount']))
                        if expense_amount <= 0:
                            logger.warning(f"Skipping invalid expense amount: {expense_amount} for {expense['description']}")
                            continue
                            
                        daily_predictions['expenses'].append({
                            'description': expense['description'],
                            'amount': float(expense_amount),  # Convert to float for JSON serialization
                            'is_fixed': True,
                            'confidence': 0.95,
                            'interval_days': interval_days,
                            'next_due_date': (current_date_iter + timedelta(days=interval_days)).strftime('%Y-%m-%d')
                        })
                        running_balance = running_balance - expense_amount  # Use explicit subtraction
                        
                    except (TypeError, ValueError, KeyError) as e:
                        logger.error(f"Error processing fixed expense: {str(e)}")
                        continue
            
            # Format expenses into separate predictions entries
            for expense in daily_predictions.get('expenses', []):
                try:
                    formatted_expense = {
                        'date': daily_predictions['date'],
                        'type': 'payment',
                        'amount': float(expense['amount']),  # Already converted to float above
                        'description': expense.get('description', 'Unknown'),
                        'party': expense.get('description', 'Unknown'),
                        'confidence': expense.get('confidence', 0.95),
                        'running_balance': running_balance,  # Use the current running balance
                        'is_fixed': expense.get('is_fixed', False),
                        'transaction_type': 'outflow'
                    }
                    formatted_predictions.append(formatted_expense)
                except (KeyError, ValueError) as e:
                    print(f"Error processing expense: {e}")
                    continue
                    
            daily_predictions['running_balance'] = running_balance
            formatted_predictions.append(daily_predictions)
            
            current_date_iter += timedelta(days=1)
            
            # Update the overall running balance for the next day
            running_balance = daily_predictions['running_balance']
        
        # Calculate insights and statistics
        if not formatted_predictions:
            total_receipts = 0
            total_payments = 0
            net_cashflow = 0
            receipts = []
            payments = []
        else:
            total_receipts = sum(p['amount'] for p in formatted_predictions if p.get('type') == 'receipt')
            total_payments = sum(p['amount'] for p in formatted_predictions if p.get('type') == 'payment')
            net_cashflow = total_receipts - total_payments
            
            # Group predictions by type for analysis
            receipts = [p for p in formatted_predictions if p.get('type') == 'receipt']
            payments = [p for p in formatted_predictions if p.get('type') == 'payment']
        
        # Calculate min and max balances
        balances = [p['running_balance'] for p in formatted_predictions if p.get('running_balance') is not None]
        min_balance = min(balances) if balances else initial_balance
        max_balance = max(balances) if balances else initial_balance
        
        # Calculate high confidence predictions
        high_confidence_receipts = [p for p in receipts if p['confidence'] >= 0.7]
        high_confidence_payments = [p for p in payments if p['confidence'] >= 0.7]
        
        # Get unique parties
        receipt_parties = {p.get('party', 'Unknown') for p in receipts}
        payment_parties = {p.get('description', 'Unknown') for p in payments}  # Use description for payments
        
        # Prepare insights
        insights = {
            'cash_position': {
                'initial_balance': initial_balance,
                'projected_final_balance': formatted_predictions[-1]['running_balance'] if formatted_predictions else initial_balance,
                'min_balance': min_balance,
                'max_balance': max_balance,
                'net_change': net_cashflow
            },
            'cashflow_summary': {
                'total_inflow': total_receipts,
                'total_outflow': total_payments,
                'net_cashflow': net_cashflow,
                'daily_average_inflow': round(total_receipts / days if days > 0 else 0, 2),
                'daily_average_outflow': round(total_payments / days if days > 0 else 0, 2)
            },
            'activity_metrics': {
                'total_transactions': len(formatted_predictions),
                'unique_payers': len(receipt_parties),
                'unique_payees': len(payment_parties),
                'high_confidence_receipts': len(high_confidence_receipts),
                'high_confidence_payments': len(high_confidence_payments)
            }
        }
        
    # Sort predictions by date and then by transaction type (inflows before outflows)
    # Sort predictions by date and type (ensuring type exists)
    formatted_predictions.sort(key=lambda x: (
        x['date'], 
        x.get('transaction_type', 'outflow') != 'inflow'
    ))
    
    # Group predictions by date for the graph
    daily_summary = {}
    for pred in formatted_predictions:
        date = pred['date']
        if date not in daily_summary:
            daily_summary[date] = {
                'date': date,
                'closing_balance': pred['running_balance'],
                'inflows': [],
                'outflows': [],
                'net_change': 0
            }
        
        if pred['type'] == 'receipt':
            daily_summary[date]['inflows'].append({
                'amount': pred['amount'],
                'party': pred['party'],
                'confidence': pred['confidence']
            })
            daily_summary[date]['net_change'] += pred['amount']
        else:
            daily_summary[date]['outflows'].append({
                'amount': pred['amount'],
                'description': pred['description'],
                'confidence': pred['confidence'],
                'is_fixed': pred.get('is_fixed', False)
            })
            daily_summary[date]['net_change'] -= pred['amount']
        
        # Convert daily summary to list and sort by date
        daily_cashflow = sorted(daily_summary.values(), key=lambda x: x['date'])
        
        # Limit predictions to avoid large payloads (frontend/network errors)
        MAX_PREDICTIONS = 200
        limited_predictions = formatted_predictions[:MAX_PREDICTIONS]
        
        response_data = {
            'initial_balance': initial_balance,
            'company_id': company_id,
            'predictions': limited_predictions,
            'daily_cashflow': daily_cashflow,  # Add daily summary for the graph
            'lastUpdated': timezone.now().isoformat(),
            'dataPoints': {
                'totalPredictions': len(limited_predictions),
                'totalParties': len(receipt_parties) + len(payment_parties),
                'fixedExpenses': len([p for p in payments if p.get('is_fixed', False)])
            },
            'balance_range': {
                'min': min_balance,
                'max': max_balance,
                'average': sum(balances) / len(balances) if balances else initial_balance
            }
        }
        
        # Include insights if requested
        if include_stats:
            response_data['insights'] = insights
        
        # Add metadata to response
        response_data['metadata'] = {
            'generated_at': timezone.now().isoformat(),
            'prediction_period': {
                'start_date': current_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'days': days
            },
            'data_points': {
                'total_transactions': len(formatted_predictions),
                'parties_analyzed': len(all_parties),
                'fixed_expenses': len(fixed_expenses)
            },
            'cache_info': {
                'cached': False,
                'cache_key': cache_key,
                'cache_expires': timezone.now() + timedelta(hours=1)
            }
        }
        
        # Prepare final response
        final_response = {
            'status': 'success',
            'data': response_data
        }
        
        # Cache the response for 1 hour and return
        try:
            cache.set(cache_key, final_response, timeout=3600)
            return Response(final_response)
        except Exception as e:
            logger.error(f"Failed to cache response: {str(e)}")
            # Return the response regardless of caching success
            return Response(final_response)
        except Exception as e:
            error_msg = log_error(e, "Error in payment predictions")
            return Response({
                'status': 'error',
                'message': error_msg,
                'details': {
                    'error_type': type(e).__name__,
                'context': 'Error occurred while generating predictions'
            }
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unpaid_sales(request, company_id=None):
    """
    Get all unpaid sales with their predicted payment dates
    """
    logger.info("Processing unpaid sales request")
    try:
        # Support both URL param and query param
        company_id = company_id or request.GET.get('company_id')
        logger.debug(f"Processing unpaid sales request for company_id: {company_id}")
        
        if not company_id:
            logger.warning("Missing company_id parameter")
            return Response({
                'status': 'error',
                'message': 'company_id parameter is required'
            }, status=400)
            
        # Validate company data
        try:
            validate_company_id(company_id)
        except ValueError as e:
            logger.error(f"Company validation failed: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)
            
        analyzer = PaymentPatternAnalyzer(company_id)
        
        # Analyze payment patterns first
        logger.debug("Starting payment pattern analysis")
        analyzer.analyze_payment_patterns()
        
        # Get unpaid sales
        logger.debug("Detecting unpaid sales")
        unpaid_sales = analyzer.detect_unpaid_sales()
        
        # Get payment predictions for unpaid sales
        logger.debug("Getting payment predictions")
        payment_predictions = analyzer.predict_payment_dates()
        
        # Combine unpaid sales with predictions
        enhanced_unpaid_sales = []
        for sale in unpaid_sales:
            # Find matching prediction
            prediction = next((p for p in payment_predictions if p['sale_id'] == sale['id']), None)
            
            enhanced_sale = {
                'id': sale['id'],
                'date': sale['date'].strftime('%Y-%m-%d') if hasattr(sale['date'], 'strftime') else sale['date'],
                'amount': sale['amount'],
                'remaining_amount': sale['remaining_amount'],
                'party_name': sale['party_name'],
                'voucher_number': sale['voucher_number'],
                'predicted_payment_date': prediction['predicted_payment_date'] if prediction else None,
                'confidence': prediction['confidence'] if prediction else 0,
                'avg_delay_days': prediction['avg_delay_days'] if prediction else 0
            }
            enhanced_unpaid_sales.append(enhanced_sale)
        
        return Response({
            'status': 'success',
            'data': {
                'unpaid_sales': enhanced_unpaid_sales,
                'total_unpaid_amount': sum(sale['remaining_amount'] for sale in enhanced_unpaid_sales),
                'total_unpaid_count': len(enhanced_unpaid_sales)
            }
        })
        
    except Exception as e:
        import traceback
        print(f"Error in unpaid sales: {str(e)}")
        print(traceback.format_exc())
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_party_balances(request, company_id=None):
    """
    Get current balances for all parties
    """
    try:
        # Support both URL param and query param
        company_id = company_id or request.query_params.get('company_id')
        
        if not company_id:
            return Response({
                'status': 'error',
                'message': 'company_id parameter is required'
            }, status=400)
            
        analyzer = PaymentPatternAnalyzer(company_id)
        
        # Analyze payment patterns first
        analyzer.analyze_payment_patterns()
        
        # Get party balances
        party_balances = analyzer.calculate_party_balances()
        
        # Enhance with payment predictions
        enhanced_balances = []
        for balance in party_balances:
            party_name = balance['party_name']
            
            # Get payment pattern for this party
            pattern = analyzer.payment_patterns.get(party_name, {})
            
            enhanced_balance = {
                'party_name': party_name,
                'current_balance': balance['current_balance'],
                'payment_probability': balance['payment_probability'],
                'avg_payment_days': pattern.get('avg_delay', 0),
                'confidence': pattern.get('confidence', 0),
                'sample_size': pattern.get('sample_size', 0)
            }
            enhanced_balances.append(enhanced_balance)
            
        return Response({
            'status': 'success',
            'data': {
                'party_balances': enhanced_balances,
                'total_outstanding': sum(balance['current_balance'] for balance in enhanced_balances),
                'total_parties': len(enhanced_balances)
            }
        })
            
    except Exception as e:
        logger.error(f"Error in party balances: {str(e)}")
        error_msg = log_error(e, "Error retrieving party balances")
        return Response({
            'status': 'error',
            'message': error_msg,
            'details': {
                'error_type': type(e).__name__,
                'context': 'Error occurred while calculating party balances'
            }
        }, status=500)
        
    # Calculate expected payment date if we have pattern
    if pattern.get('avg_delay'):
        current_date = timezone.now().date()
        expected_date = current_date + timedelta(days=pattern['avg_delay'])
        enhanced_balance['expected_payment_date'] = expected_date.strftime('%Y-%m-%d')
        enhanced_balance['payment_probability'] = pattern['confidence']

        return Response({
            'status': 'success',
            'data': {
                'party_balances': enhanced_balances,
                'total_outstanding': sum(balance['current_balance'] for balance in enhanced_balances),
                'total_parties': len(enhanced_balances)
            }
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_analysis_summary(request, company_id=None):
    """
    Get comprehensive payment analysis summary
    """
    logger.info("Processing payment analysis summary request")
    try:
        # Support both URL param and query param
        company_id = company_id or request.GET.get('company_id')
        logger.debug(f"Processing payment analysis summary for company_id: {company_id}")
        
        if not company_id:
            logger.warning("Missing company_id parameter")
            return Response({
                'status': 'error',
                'message': 'company_id parameter is required'
            }, status=400)
            
        # Validate company data
        try:
            validate_company_id(company_id)
        except ValueError as e:
            logger.error(f"Company validation failed: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)
            
        analyzer = PaymentPatternAnalyzer(company_id)
        
        # Run all analyses with proper logging
        logger.debug("Starting comprehensive analysis")
        payment_patterns = analyzer.analyze_payment_patterns()
        logger.debug(f"Found {len(payment_patterns) if payment_patterns else 0} payment patterns")
        
        fixed_expenses = analyzer.analyze_fixed_expenses()
        logger.debug(f"Found {len(fixed_expenses) if fixed_expenses else 0} fixed expenses")
        
        unpaid_sales = analyzer.detect_unpaid_sales()
        logger.debug(f"Found {len(unpaid_sales)} unpaid sales")
        
        payment_predictions = analyzer.predict_payment_dates()
        logger.debug(f"Generated {len(payment_predictions)} payment predictions")
        
        party_balances = analyzer.calculate_party_balances()
        logger.debug(f"Calculated balances for {len(party_balances)} parties")
        
        # Calculate summary statistics
        total_unpaid_amount = sum(sale['remaining_amount'] for sale in unpaid_sales)
        total_outstanding_balance = sum(balance['current_balance'] for balance in party_balances)
        
        # Get high confidence predictions
        high_confidence_predictions = [p for p in payment_predictions if p['confidence'] >= 0.7]
        total_high_confidence_amount = sum(p['remaining_amount'] for p in high_confidence_predictions)
        
        summary = {
            'payment_patterns': {
                'total_parties': len(payment_patterns),
                'parties_with_patterns': len([p for p in payment_patterns if isinstance(p, dict) and p.get('sample_size', 0) > 0]),
                'average_payment_delay': (sum(p.get('avg_payment_days', 0) for p in payment_patterns if isinstance(p, dict)) / 
                                      len(payment_patterns) if payment_patterns else 0)
            },
            'unpaid_sales': {
                'total_count': len(unpaid_sales),
                'total_amount': total_unpaid_amount,
                'average_amount': total_unpaid_amount / len(unpaid_sales) if unpaid_sales else 0
            },
            'payment_predictions': {
                'total_predictions': len(payment_predictions),
                'high_confidence_predictions': len(high_confidence_predictions),
                'total_predicted_amount': sum(p['remaining_amount'] for p in payment_predictions),
                'high_confidence_amount': total_high_confidence_amount
            },
            'party_balances': {
                'total_parties': len(party_balances),
                'total_outstanding': total_outstanding_balance,
                'average_outstanding': total_outstanding_balance / len(party_balances) if party_balances else 0
            },
            'fixed_expenses': {
                'total_expenses': len(fixed_expenses),
                'total_monthly_amount': sum(e['amount'] for e in fixed_expenses.values())
            }
        }
        
        return Response({
            'status': 'success',
            'data': summary
        })
        
    except Exception as e:
        logger.error(f"Error in payment analysis summary: {str(e)}")
        error_msg = log_error(e, "Error in payment analysis summary")
        return Response({
            'status': 'error',
            'message': error_msg,
            'details': {
                'error_type': type(e).__name__,
                'context': 'Error occurred while generating payment analysis summary'
            }
        }, status=500)
