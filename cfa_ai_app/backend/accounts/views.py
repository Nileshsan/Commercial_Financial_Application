from django.shortcuts import render
from django.db import models
from rest_framework import status, viewsets, mixins, permissions, authentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
import math
from datetime import datetime
import os
import json
import logging
from .models import (
    Company, Client, LedgerGroup, LedgerBalance, LedgerOpeningBalance, UserCompany
)
from transactions.models import LedgerEntry
from transactions.models import TallyTransaction
from .authentication import CompanyAPIKeyAuthentication, BearerTokenAuthentication

@api_view(['POST', 'OPTIONS'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login endpoint that returns authentication token and user info
    """
    if request.method == 'OPTIONS':
        return Response(status=status.HTTP_200_OK)

    # Extract credentials
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    # Validate input
    if not username or not password:
        return Response({
            'status': 'error',
            'message': 'Please provide both username and password'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Authenticate user
        user = authenticate(username=username, password=password)
        
        if not user:
            return Response({
                'status': 'error',
                'message': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({
                'status': 'error',
                'message': 'Account is disabled'
            }, status=status.HTTP_403_FORBIDDEN)

        # Get or create auth token
        auth_token, created = Token.objects.get_or_create(user=user)
        
        # If token was not created just now, update it for security
        if not created:
            auth_token.delete()
            auth_token = Token.objects.create(user=user)

        # Get user's company directly from the user model
        company = user.company
        user_company = user.user_company
        
        response_data = {
            'status': 'success',
            'data': {
                'token': auth_token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'company_id': company.id if company else None,
                    'company_name': company.name if company else None,
                    'user_company_name': user_company.name if user_company else None,
                    'role': user.role
                }
            }
        }
        return Response(response_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_user_api_token(request):
    """
    Get API token for the authenticated user
    """
    try:
        # Get user from authenticated request
        user = request.user
        if not user.is_authenticated:
            return Response({
                'status': 'error',
                'message': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Get company directly from user
        company = user.company
        user_company = user.user_company

        if not company:
            return Response({
                'status': 'error',
                'message': 'No company associated with user'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate API token if it doesn't exist
        if not company.api_key:
            company.api_key = company.generate_api_key()
            company.save()

        return Response({
            'status': 'success',
            'data': {
                'api_token': company.api_key,
                'company_name': company.name,
                'user_company_name': user_company.name if user_company else None
            }
        }, status=status.HTTP_200_OK)
        
        api_token = company.api_key
        if not api_token:
            # Generate API token if it doesn't exist
            api_token = company.generate_api_key()
            company.save()
        
        return Response({
            'status': 'success',
            'data': {
                'api_token': api_token,
                'company_name': company.name,
                'user_company_name': company.user_company.name
            }
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def check_model_status(request):
    """
    Check if the AI model is trained and ready
    """
    try:
        # For now, return that model is ready
        # In a real implementation, this would check the actual model status
        return Response({
            'status': 'success',
            'data': {
                'isReady': True
            }
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def train_model(request):
    """
    Start model training process
    """
    try:
        # For now, just return success
        # In a real implementation, this would start the actual training process
        return Response({
            'status': 'success',
            'message': 'Model training started successfully'
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def logout_view(request):
    """
    Logout endpoint that invalidates the auth token
    """
    if request.auth:
        request.auth.delete()
    return Response({'status': 'success'})

class CompanyAuthMixin:
    """
    Mixin to add company identification from auth token.
    Use this in views that need to associate data with a company.
    """
    permission_classes = [AllowAny]
    
    def get_company_from_token(self, request):
        logger = logging.getLogger('cfa.auth')
        # Get company info from auth token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            logger.error("No Bearer token provided")
            raise AuthenticationFailed({
                'error': 'Authorization token required',
                'detail': 'Please provide a valid Bearer token'
            })
            
        token_key = auth_header.split(' ')[1]
        try:
            # Get token with related user and company info
            token = Token.objects.select_related(
                'user',
                'user__company',
                'user__user_company'
            ).get(key=token_key)
            
            user = token.user
            company = user.company
            user_company = user.user_company
            
            if not company or not user_company:
                logger.error(f"User {user.username} not properly associated with company")
                raise AuthenticationFailed({
                    'error': 'Company association error',
                    'detail': 'User is not properly associated with a company'
                })
            
            logger.info(f"Authenticated user: {user.username}")
            logger.info(f"Company: {company.name}")
            logger.info(f"User Company: {user_company.name}")
            
            return {
                'user': user,
                'company': company,
                'user_company': user_company
            }
            
        except Token.DoesNotExist:
            logger.error(f"Invalid token: {token_key}")
            raise AuthenticationFailed({
                'error': 'Invalid authorization token',
                'detail': 'The provided token is not valid'
            })
        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            raise AuthenticationFailed({
                'error': 'Authorization error',
                'detail': str(e)
            })

class TallyDataImportView(CompanyAuthMixin, viewsets.GenericViewSet, mixins.CreateModelMixin):
    """
    ViewSet for importing Tally data with automatic company association using auth token.
    """
    queryset = TallyTransaction.objects.all()
    
    def create(self, request, *args, **kwargs):
        try:
            auth_info = self.get_company_from_token(request)
            company = auth_info['company']
        except AuthenticationFailed as e:
            return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)
            
        # Your existing tally data import logic here, but now you have the company
        data = request.data
        
        # Example: Create transaction with company automatically set
        transaction_data = {
            'voucher_no': data.get('voucher_no'),
            'date': data.get('date'),
            'party_name': data.get('party_name'),
            'amount': data.get('amount'),
            'register_type': data.get('register_type'),
            'company': company  # Automatically set the company
        }
        
        transaction = TallyTransaction.objects.create(**transaction_data)
        
        return Response({
            'status': 'success',
            'message': 'Transaction created',
            'transaction_id': transaction.id
        })
    

@api_view(['GET'])
@permission_classes([AllowAny])
def get_client_balances(request):
    """
    Get each client's opening balance, total transaction amount, and current balance.
    Handles both types of Tally data: transactions and ledger balances.
    """
    try:
        # Get all unique names from both transactions and ledger balances
        party_names = set(TallyTransaction.objects.values_list('party_name', flat=True))
        party_names.update(LedgerBalance.objects.values_list('ledger_name', flat=True))
        
        result = []
        for party in party_names:
            # Get opening balance from ledger balances
            opening_qs = LedgerBalance.objects.filter(ledger_name=party)
            opening_balance = sum(float(ob.opening_balance or 0.0) for ob in opening_qs)
            
            # Get transaction totals
            transactions = TallyTransaction.objects.filter(party_name=party)
            
            # Calculate transaction totals based on party type and register type
            transaction_total = 0.0
            for tx in transactions:
                amount = float(tx.amount or 0.0)
                if tx.party_type == 'customer':
                    if tx.register_type in ['sales', 'debit_note']:
                        transaction_total += amount
                    elif tx.register_type in ['receipt', 'credit_note']:
                        transaction_total -= amount
                elif tx.party_type == 'vendor':
                    if tx.register_type in ['purchase', 'debit_note']:
                        transaction_total -= amount
                    elif tx.register_type in ['payment', 'credit_note']:
                        transaction_total += amount
                # For journal entries, use the sign of the amount directly
                elif tx.register_type == 'journal':
                    transaction_total += amount
            
            # Determine party type from ledger group if available
            party_type = 'other'
            if opening_qs.exists():
                group_name = opening_qs.first().group.name.lower()
                if any(term in group_name for term in ['sundry debtor', 'debtor']):
                    party_type = 'customer'
                elif any(term in group_name for term in ['sundry creditor', 'creditor']):
                    party_type = 'vendor'
            else:
                # Try to get party type from transactions
                tx = transactions.first()
                if tx:
                    party_type = tx.party_type
            
            # Current balance
            current_balance = opening_balance + transaction_total
            
            result.append({
                'client_name': party,
                'party_type': party_type,
                'opening_balance': opening_balance,
                'transaction_total': transaction_total,
                'current_balance': current_balance,
            })
            
        return Response({'clients': result}, status=200)
    except Exception as e:
        return Response({'error': f'Error aggregating client balances: {str(e)}'}, status=500)
import json
from datetime import datetime
import math
from django.db import models  # type: ignore
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, authentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from django.db import transaction as db_transaction
import logging



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def receive_tally_transactions(request):
    """
    Receive Tally transactions from the sync agent and store them grouped by company, including all ledger entries.
    Company information is extracted from the authenticated user's token.
    """
    import logging
    logger = logging.getLogger('tally_transaction_import')
    logger.info("="*80)
    logger.info("TRANSACTION SYNC STARTED")
    logger.info(f"Headers: {request.headers}")
    
    # Get company information from authenticated user
    user = request.user
    user_company = getattr(user, 'user_company', None)
    company = getattr(user, 'company', None)
    
    if not user_company:
        logger.error("User is not associated with a user company")
        return Response({'error': 'User is not associated with a user company'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not company:
        logger.error("User is not associated with a company")
        return Response({'error': 'User is not associated with a company'}, status=status.HTTP_400_BAD_REQUEST)
    
    logger.info(f"Processing transactions for User Company: {user_company.name}, Company: {company.name}")
    
    try:
        data = request.data
        logger.info(f"[receive_tally_transactions] Raw request data type: {type(request.data)}")
        logger.info(f"[receive_tally_transactions] Request Content-Type: {request.content_type}")
        
        # Validate request data
        if not data:
            logger.error("[receive_tally_transactions] No data received in request")
            return Response({'error': 'No data received'}, status=status.HTTP_400_BAD_REQUEST)
            
        if isinstance(data, dict):
            # Try to extract list from dictionary
            for key in ['data', 'transactions', 'vouchers']:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    logger.info(f"[receive_tally_transactions] Extracted list from key: {key}")
                    break
                    
        if not isinstance(data, list):
            logger.error(f"[receive_tally_transactions] Payload is not a list. Type: {type(data)}")
            return Response({'error': 'Data must be a list of transactions'}, status=status.HTTP_400_BAD_REQUEST)
            
        logger.info(f"[receive_tally_transactions] Number of transactions in payload: {len(data)}")
        logger.debug(f"[receive_tally_transactions] First transaction sample: {data[0] if data else 'No data'}")
        
        transactions_created = 0
        companies_created = 0
        errors = []
        skipped = 0
        with transaction.atomic():
            for idx, transaction_data in enumerate(data):
                logger.info(f"[receive_tally_transactions] Processing idx={idx}: {transaction_data}")
                # Extract all possible party name sources
                party_raw = None
                
                # Try all possible party name fields
                possible_party_fields = [
                    'party_name',              # Standard field
                    'party_ledger_name',       # Alternative field
                    'account_name',            # Another possible field
                    'ledger_name',             # Sometimes used directly
                    'sundry_debtor_name',      # For customer transactions
                    'sundry_creditor_name',    # For vendor transactions
                ]
                
                # Try to get party name from main fields first
                for field in possible_party_fields:
                    if transaction_data.get(field):
                        party_raw = transaction_data.get(field)
                        logger.info(f"Found party name in field: {field}")
                        break
                
                # If no party name found in main fields, try to get ledger name
                if not party_raw and transaction_data.get('ledger_name'):
                    party_raw = transaction_data.get('ledger_name')
                    logger.info(f"Using ledger_name as party name: {party_raw}")
                
                # If still no party name, try ledger entries
                if not party_raw:
                    ledger_entries = transaction_data.get('ledger_entries', [])
                    for le in ledger_entries:
                        # Check multiple indicators for party ledger
                        if (le.get('is_party_ledger') or 
                            le.get('is_party') or 
                            le.get('all_fields', {}).get('ISPARTYLEDGER') in [True, 'Yes', 'yes', 'YES', '1', 1] or
                            'sundry' in le.get('group', '').lower()):
                            
                            # Try multiple fields in ledger entry
                            for field in possible_party_fields:
                                if le.get(field):
                                    party_raw = le.get(field)
                                    logger.info(f"Found party name in ledger entry field: {field}")
                                    break
                            
                            # If no party name found in fields, use ledger_name from the entry
                            if not party_raw and le.get('ledger_name'):
                                party_raw = le.get('ledger_name')
                                logger.info(f"Using ledger entry's ledger_name as party name: {party_raw}")
                            
                            if party_raw:
                                break
                
                amount_raw = transaction_data.get('amount')
                date_raw = transaction_data.get('date')
                
                logger.info(f"Party name extraction result - Raw: {party_raw}")

                # Enhanced Party Name validation with detailed checks
                try:
                    if party_raw is None:
                        party_name = ''
                        logger.warning(f'Transaction {idx}: Party raw is None')
                    elif isinstance(party_raw, (str, int, float)):
                        party_name = str(party_raw).strip()
                        logger.info(f'Transaction {idx}: Successfully extracted party name: {party_name}')
                    else:
                        # Try to convert complex objects to string
                        try:
                            party_name = str(party_raw).strip()
                            logger.warning(f'Transaction {idx}: Converted complex party_raw to string: {party_name}')
                        except:
                            party_name = ''
                            logger.error(f'Transaction {idx}: Could not convert party_raw to string: {type(party_raw)}')
                except (AttributeError, TypeError) as e:
                    party_name = ''
                    logger.error(f'Transaction {idx}: Party name extraction failed: {str(e)}, party_raw: {party_raw}')
                    
                if not party_name:
                    # Enhanced party name extraction from ledger entries with better null handling
                    ledger_entries = transaction_data.get('ledger_entries', [])
                    for le in ledger_entries:
                        try:
                            # Check for party ledger indicators
                            is_party = le.get('is_party_ledger', False)
                            if not is_party:
                                all_fields = le.get('all_fields', {})
                                if isinstance(all_fields, dict):  # Ensure all_fields is a dict before accessing
                                    is_party = all_fields.get('ISPARTYLEDGER') in [True, 'Yes', 'yes', 'YES', '1', 1]
                            
                            if is_party:
                                raw_ledger_name = le.get('ledger_name')
                                if raw_ledger_name is not None:  # Explicit None check
                                    party_name = str(raw_ledger_name).strip()
                                    if party_name:  # Only break if we got a valid name
                                        logger.info(f"Found party name '{party_name}' in ledger entries")
                                        break
                        except Exception as e:
                            logger.warning(f"Error processing ledger entry: {str(e)}")
                
                logger.info(f"Processing transaction - Party: {party_name}, Amount: {amount_raw}, Date: {date_raw}")
                logger.info(f"Company Context: user_company={user_company.name}, company={company.name}")

                # Critical data validation with detailed error messages
                # Validate critical transaction data
                validation_errors = []
                
                # 1. Party Name Validation (Most Critical)
                if not party_name:
                    # Log detailed information about the failed transaction
                    logger.error(f"Transaction {idx}: Party name extraction failed")
                    logger.error(f"Transaction data: {transaction_data}")
                    logger.error(f"Voucher type: {transaction_data.get('voucher_type', 'unknown')}")
                    logger.error(f"Register type: {register_type}")
                    
                    error_msg = (f'Transaction {idx}: Missing party name. '
                               f'Voucher type: {transaction_data.get("voucher_type", "unknown")}, '
                               f'Register: {register_type}. Cannot process transaction without party identification.')
                    logger.error(error_msg)
                    validation_errors.append(error_msg)
                    
                    # Log available ledger entries for debugging
                    ledger_entries = transaction_data.get('ledger_entries', [])
                    if ledger_entries:
                        logger.error(f"Available ledger entries:")
                        for i, le in enumerate(ledger_entries):
                            logger.error(f"Ledger {i}: Name: {le.get('ledger_name')}, "
                                       f"Group: {le.get('group')}, "
                                       f"IsParty: {le.get('is_party_ledger')}")
                
                # 2. Amount Validation (Critical)
                try:
                    if amount_raw in [None, '', ' ']:
                        # Try to calculate from ledger entries
                        ledger_entries = transaction_data.get('ledger_entries', [])
                        amount = sum(float(le.get('amount', 0.0) or 0.0) for le in ledger_entries)
                        if amount == 0:
                            validation_errors.append(f'Transaction {idx}: No valid amount found in transaction or ledger entries')
                    else:
                        amount = float(amount_raw)
                        if amount == 0:
                            logger.warning(f'Transaction {idx}: Zero amount transaction for party {party_name}')
                except (ValueError, TypeError) as e:
                    error_msg = f'Transaction {idx}: Invalid amount format: {amount_raw}'
                    logger.error(error_msg)
                    validation_errors.append(error_msg)
                
                # 3. Date Validation (Critical)
                if not date_raw:
                    error_msg = f'Transaction {idx}: Missing transaction date'
                    logger.error(error_msg)
                    validation_errors.append(error_msg)
                
                # If any critical validation failed, skip this transaction
                if validation_errors:
                    for error in validation_errors:
                        errors.append(error)
                    logger.error(f"Skipping transaction {idx} due to validation errors")
                    skipped += 1
                    continue
                
                logger.info(f"✓ Validation passed for transaction {idx} - Party: {party_name}, Amount: {amount}, Date: {date_raw}")

                # Use company information from authenticated user (already validated above)
                logger.info(f"Using company from authenticated user: {company.name} (User Company: {user_company.name})")
                # Enhanced date parsing with multiple format support
                date_str = str(date_raw) if date_raw else ''
                date_obj = None
                if date_str:
                    # List of possible date formats to try
                    date_formats = [
                        '%Y%m%d',       # 20250726
                        '%d/%m/%Y',     # 26/07/2025
                        '%Y-%m-%d',     # 2025-07-26
                        '%d-%m-%Y',     # 26-07-2025
                        '%d%m%Y',       # 26072025
                        '%Y/%m/%d',     # 2025/07/26
                    ]
                    
                    for date_format in date_formats:
                        try:
                            date_obj = datetime.strptime(date_str, date_format).date()
                            logger.info(f"Successfully parsed date {date_str} using format {date_format}")
                            break
                        except ValueError:
                            continue
                    
                    if not date_obj:
                        error_msg = f'Transaction {idx}: Could not parse date {date_str} in any known format'
                        logger.error(error_msg)
                        errors.append(error_msg)
                        date_obj = datetime.now().date()
                else:
                    logger.warning(f'Transaction {idx}: No date provided, using current date')
                    date_obj = datetime.now().date()
                
                # Validate date is not in future
                if date_obj > datetime.now().date():
                    logger.warning(f'Transaction {idx}: Future dated transaction detected for {party_name} on {date_obj}')
                # Map voucher_type to register_type
                voucher_type = transaction_data.get('voucher_type', '').lower()
                register_type_map = {
                    'sales': 'sales',
                    'purchase': 'purchase',
                    'payment': 'payment',
                    'receipt': 'receipt',
                    'journal': 'journal',
                    'credit note': 'credit_note',
                    'debit note': 'debit_note',
                }
                register_type = register_type_map.get(voucher_type, 'journal')
                # Enhanced amount handling with better null checking and validation
                amount = 0.0  # Default amount
                raw_amount = transaction_data.get('amount')
                
                # First try to get amount from main transaction data
                if raw_amount not in [None, '', ' ']:
                    try:
                        amount = float(str(raw_amount).strip() or '0.0')
                        logger.info(f'Transaction {idx}: Successfully parsed amount: {amount}')
                    except (ValueError, TypeError, AttributeError) as ex:
                        logger.warning(f'Transaction {idx}: Could not parse amount {raw_amount}, using 0.0. Error: {ex}')
                        amount = 0.0
                else:
                    # If no amount in main data, try to sum ledger entries
                    try:
                        ledger_entries = transaction_data.get('ledger_entries', [])
                        if ledger_entries:
                            amount = sum(float(str(le.get('amount', '0.0')).strip() or '0.0') for le in ledger_entries)
                            logger.info(f'Transaction {idx}: Calculated amount {amount} from ledger entries')
                        else:
                            logger.warning(f'Transaction {idx}: No amount and no ledger entries, using 0.0')
                    except Exception as ex:
                        logger.error(f'Transaction {idx}: Error calculating amount from ledger entries: {ex}')
                        amount = 0.0
                
                # Final validation to ensure we have a valid float
                if not isinstance(amount, float) or math.isnan(amount):
                    logger.warning(f'Transaction {idx}: Invalid amount type or NaN, setting to 0.0')
                    amount = 0.0
                try:
                    # Extract detailed transaction information
                    voucher_id = transaction_data.get('voucher_id', '')
                    reference_no = transaction_data.get('reference_no', '')
                    payment_mode = transaction_data.get('payment_mode', '')
                    due_date = None
                    
                    # Parse due date if available
                    due_date_str = transaction_data.get('due_date', '')
                    if due_date_str:
                        try:
                            if len(due_date_str) == 8 and due_date_str.isdigit():
                                due_date = datetime.strptime(due_date_str, '%Y%m%d').date()
                            elif '/' in due_date_str:
                                due_date = datetime.strptime(due_date_str, '%d/%m/%Y').date()
                            else:
                                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                        except Exception as ex:
                            logger.warning(f'Invalid due date format {due_date_str}, skipping. Error: {ex}')

                    # Create enhanced transaction record with payment behavior tracking
                    # Ensure all fields have safe default values
                    safe_voucher_no = str(transaction_data.get('voucher_no', '') or '').strip()
                    safe_voucher_id = str(voucher_id or '').strip()
                    safe_party_name = str(party_name or '').strip() or 'Unknown Party'
                    safe_party_type = str(transaction_data.get('party_type', '') or '').strip().lower() or 'other'
                    safe_narration = str(transaction_data.get('narration', '') or '').strip()
                    safe_payment_mode = str(payment_mode or '').strip()
                    safe_reference_no = str(reference_no or '').strip()
                    safe_register_type = str(register_type or '').strip().lower() or 'journal'
                    
                    # Ensure amount is a valid float
                    safe_amount = float(amount if isinstance(amount, (int, float)) else 0.0)
                    if math.isnan(safe_amount) or math.isinf(safe_amount):
                        safe_amount = 0.0
                        logger.warning(f'Transaction {idx}: Invalid amount detected, using 0.0')
                    
                    # Check if transaction already exists
                    existing_txn = TallyTransaction.objects.filter(
                        voucher_no=safe_voucher_no,
                        register_type=safe_register_type,
                        company=company
                    ).first()
                    
                    if existing_txn:
                        # Log the duplicate and skip
                        logger.info(f'Skipping duplicate transaction - Voucher: {safe_voucher_no}, Type: {safe_register_type}')
                        continue
                        
                    # Create new transaction if it doesn't exist
                    txn = TallyTransaction.objects.create(
                        voucher_no=safe_voucher_no,
                        voucher_id=safe_voucher_id,
                        date=date_obj or datetime.now().date(),
                        due_date=due_date,
                        party_name=safe_party_name,
                        party_type=safe_party_type,
                        narration=safe_narration,
                        amount=safe_amount,
                        register_type=safe_register_type,
                        payment_mode=safe_payment_mode,
                        reference_no=safe_reference_no,
                        company=company,
                        payment_status='pending' if due_date and due_date > datetime.now().date() else 'completed'
                    )
                    
                    # If this is opening balance data, also create LedgerBalance records
                    if register_type == 'opening_balance':
                        # Get or create ledger group
                        group_name = transaction_data.get('group', '')
                        group_category = 'asset' if 'debtor' in group_name.lower() else 'liability' if 'creditor' in group_name.lower() else 'other'
                        ledger_group, _ = LedgerGroup.objects.get_or_create(
                            name=group_name,
                            company=company,
                            defaults={'category': group_category}
                        )
                        
                        # Create ledger balance record with safe values
                        safe_ledger_name = str(party_name or '').strip() or 'Unknown Ledger'
                        safe_balance = float(amount if isinstance(amount, (int, float)) else 0.0)
                        if math.isnan(safe_balance) or math.isinf(safe_balance):
                            safe_balance = 0.0
                        
                        raw_balance = transaction_data.get('raw_balance')
                        safe_raw_balance = str(raw_balance if raw_balance is not None else safe_balance).strip()
                        
                        LedgerBalance.objects.create(
                            ledger_name=safe_ledger_name,
                            group=ledger_group,
                            opening_balance=safe_balance,
                            raw_balance=safe_raw_balance,
                            company=company
                        )
                        
                except Exception as ex:
                    logger.error(f'Transaction {idx}: Error creating records: {ex}')
                    errors.append(f'Transaction {idx}: Error creating records: {ex}')
                    continue
                # For regular transactions, process the ledger entries
                if register_type != 'opening_balance':
                    for le_idx, le in enumerate(transaction_data.get('ledger_entries', [])):
                        try:
                            # Enhanced ledger group handling with null checks
                            try:
                                raw_group_name = le.get('group')
                                group_name = str(raw_group_name).strip() if raw_group_name is not None else 'Uncategorized'
                            except (AttributeError, TypeError):
                                group_name = 'Uncategorized'
                                logger.warning(f'Transaction {idx} LedgerEntry {le_idx}: Invalid group name format: {le.get("group")}')
                            
                            try:
                                raw_group_type = le.get('standardized_type')
                                group_type = str(raw_group_type).lower().strip() if raw_group_type is not None else 'other'
                            except (AttributeError, TypeError):
                                group_type = 'other'
                            
                            try:
                                ledger_group, created = LedgerGroup.objects.get_or_create(
                                    name=group_name,
                                    company=company,
                                    defaults={'category': group_type}
                                )
                                if created:
                                    logger.info(f'Created new LedgerGroup: {group_name} ({group_type})')
                            except Exception as lg_ex:
                                logger.error(f'Error creating LedgerGroup {group_name}: {str(lg_ex)}')
                                # Create a fallback group
                                ledger_group, _ = LedgerGroup.objects.get_or_create(
                                    name='Uncategorized',
                                    company=company,
                                    defaults={'category': 'other'}
                                )
                            
                            # Enhanced amount processing with null safety
                            try:
                                raw_amount = le.get('standardized_amount')
                                if raw_amount is not None:
                                    le_amount = float(str(raw_amount).strip() or '0.0')
                                else:
                                    le_amount = 0.0
                            except (ValueError, TypeError, AttributeError) as e:
                                le_amount = 0.0
                                logger.warning(f"Transaction {idx} LedgerEntry {le_idx}: Invalid amount format: {str(e)}")
                                
                            # Enhanced ledger entry processing with improved null checks
                            try:
                                raw_ledger_name = le.get('ledger_name')
                                if raw_ledger_name is not None:
                                    ledger_name = str(raw_ledger_name).strip()
                                    if not ledger_name:
                                        logger.warning(f"Transaction {idx} LedgerEntry {le_idx}: Empty ledger name after stripping")
                                else:
                                    ledger_name = ''
                                    logger.warning(f"Transaction {idx} LedgerEntry {le_idx}: Null ledger name received")
                            except (AttributeError, TypeError) as e:
                                ledger_name = ''
                                logger.warning(f"Transaction {idx} LedgerEntry {le_idx}: Invalid ledger name format: {str(e)}")
                            
                            if ledger_name and not LedgerBalance.objects.filter(
                                ledger_name=ledger_name,
                                company=company
                            ).exists():
                                try:
                                    LedgerBalance.objects.create(
                                        ledger_name=ledger_name,
                                        group=ledger_group,
                                        opening_balance=0,  # Start with 0 since this is a new ledger
                                        raw_balance='0',
                                        company=company
                                    )
                                    logger.info(f'Created new LedgerBalance for {ledger_name}')
                                except Exception as le_ex:
                                    logger.error(f'Failed to create LedgerBalance for {ledger_name}: {str(le_ex)}')
                                
                            # Update transaction with party type if needed
                            if txn.party_type == 'other' and ledger_name == txn.party_name:
                                if 'debtor' in group_name.lower():
                                    txn.party_type = 'customer'
                                elif 'creditor' in group_name.lower():
                                    txn.party_type = 'vendor'
                                txn.save()
                                
                        except Exception as ex:
                            logger.error(f'Transaction {idx} LedgerEntry {le_idx}: Error processing entry: {ex}')
                            errors.append(f'Transaction {idx} LedgerEntry {le_idx}: Error processing entry: {ex}')
                transactions_created += 1
        response_data = {
            'message': 'Transactions processed successfully',
            'transactions_created': transactions_created,
            'companies_created': companies_created,
            'errors': errors
        }
        logger.info(f'Import summary: {response_data}')
        return Response(response_data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.critical(f'Critical error processing transactions: {e}')
        return Response({'error': f'Error processing transactions: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_client_transactions(request, client_name=None):
    """
    Get all transactions for a specific client
    """
    try:
        if client_name:
            # Get transactions for specific client
            transactions = TallyTransaction.objects.filter(  # type: ignore
                party_name__icontains=client_name
            ).select_related('client')
        else:
            # Get all transactions grouped by client
            transactions = TallyTransaction.objects.all().select_related('client')  # type: ignore
        
        # Group by client
        client_data = {}
        for trans in transactions:
            client_name = trans.party_name
            if client_name not in client_data:
                client_data[client_name] = {
                    'client_name': client_name,
                    'total_transactions': 0,
                    'total_amount': 0.0,
                    'transactions': []
                }
            
            client_data[client_name]['total_transactions'] += 1
            client_data[client_name]['total_amount'] += float(trans.amount)
            client_data[client_name]['transactions'].append({
                'id': trans.id,
                'voucher_no': trans.voucher_no,
                'date': trans.date.isoformat(),
                'narration': trans.narration,
                'amount': float(trans.amount),
                'register_type': trans.register_type,
                'created_at': trans.created_at.isoformat()
            })
        
        return Response({
            'clients': list(client_data.values())
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Error retrieving transactions: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def get_clients_summary(request):
    """
    Get summary of all clients with their transaction counts and amounts
    """
    try:
        clients = Client.objects.annotate(  # type: ignore
            transaction_count=models.Count('transactions'),
            total_amount=models.Sum('transactions__amount')
        ).values('name', 'transaction_count', 'total_amount')
        
        return Response({
            'clients': list(clients)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Error retrieving clients summary: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def receive_opening_balances(request):
    """
    Receive opening balances from the agent and store them for each company.
    The company information will be taken from the authenticated user's token.
    """
    logger = logging.getLogger('opening_balances')
    
    try:
        # Get company information from the authenticated user
        user = request.user
        company = getattr(user, 'company', None)
        
        if not company:
            logger.error("User is not associated with a company")
            return Response({
                'error': 'User is not associated with a company'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        data = request.data
        if not data:
            logger.error("No data received in request")
            return Response({
                'error': 'No data received'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        success = []
        errors = []
        
        with transaction.atomic():
            for idx, balance_data in enumerate(data):
                try:
                    # Extract and validate fields
                    ledger_name = str(balance_data.get('ledger_name', '')).strip()
                    group_name = str(balance_data.get('group', '')).strip()
                    opening_balance = balance_data.get('opening_balance', 0.0)
                    
                    if not ledger_name:
                        logger.warning(f"Entry {idx}: Missing ledger name, skipping")
                        errors.append(f"Entry {idx}: Missing ledger name")
                        continue
                        
                    # Check for existing balance
                    existing = LedgerBalance.objects.filter(
                        ledger_name=ledger_name,
                        company=company
                    ).first()
                    
                    if existing:
                        logger.info(f"Entry {idx}: Updating existing balance for {ledger_name}")
                        existing.opening_balance = opening_balance
                        existing.save()
                        success.append(f"Updated balance for {ledger_name}")
                        continue
                    
                    # Create new balance entry
                    group_category = 'asset' if 'debtor' in group_name.lower() else 'liability' if 'creditor' in group_name.lower() else 'other'
                    
                    # Get or create ledger group
                    group, _ = LedgerGroup.objects.get_or_create(
                        name=group_name,
                        company=company,
                        defaults={'category': group_category}
                    )
                    
                    LedgerBalance.objects.create(
                        ledger_name=ledger_name,
                        group=group,
                        opening_balance=opening_balance,
                        company=company
                    )
                    success.append(f"Created balance for {ledger_name}")
                    
                except Exception as entry_error:
                    logger.error(f"Error processing entry {idx}: {str(entry_error)}")
                    errors.append(f"Entry {idx}: {str(entry_error)}")
                    continue
                    
        return Response({
            'status': 'success',
            'message': 'Opening balances processed',
            'success_count': len(success),
            'error_count': len(errors),
            'errors': errors[:10] if errors else None  # Return first 10 errors only
        })
        
    except Exception as e:
        logger.exception("Error processing opening balances")
        return Response({
            'error': f'Error processing opening balances: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TokenHeaderAuthentication(authentication.TokenAuthentication):
    keyword = 'Bearer'
    model = Token

    def authenticate(self, request):
        import logging
        logger = logging.getLogger('cfa.token_auth')
        auth = authentication.get_authorization_header(request).split()
        if not auth or auth[0].lower() != b'bearer':
            logger.warning('No Bearer token found in Authorization header.')
            return None
        if len(auth) == 1:
            logger.warning('Invalid Authorization header: Token missing.')
            return None
        elif len(auth) > 2:
            logger.warning('Invalid Authorization header: Too many fields.')
            return None
        try:
            token_key = auth[1].decode()
        except UnicodeError:
            logger.error('Token decode error.')
            return None
        logger.info(f'Received API key: {token_key}')
        try:
            token_obj = Token.objects.select_related('user').get(key=token_key)
        except Token.DoesNotExist:
            logger.error(f'No Token found for key: {token_key}')
            return None
        user = token_obj.user
        logger.info(f'Authenticated user: {user.username} (id={user.id}), client: {getattr(user, "client", None)}')
        if not user.is_active:
            logger.warning(f'Inactive user for token: {token_key}')
            return None
        return (user, token_obj)

logger = logging.getLogger("cfa.transactions")

class TransactionUploadView(APIView):
    authentication_classes = [TokenHeaderAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import os
        
        # Get company information from the authenticated user
        user = request.user
        company = getattr(user, 'company', None)
        
        if not company:
            return Response({'error': 'User is not associated with a company.'}, status=400)
            
        data = request.data
        # Write incoming data to a file for debugging
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transaction_logs')
        os.makedirs(log_dir, exist_ok=True)
        from datetime import datetime
        log_file = os.path.join(log_dir, f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            import json
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Robust tx_list extraction: accept any key with a list if 'data' or 'transactions' not found
        tx_list = []
        if isinstance(data, list):
            tx_list = data
        elif isinstance(data, dict):
            tx_list = data.get('data') or data.get('transactions') or data.get('vouchers')
            if not tx_list:
                # Try to find the first list value in the dict
                for v in data.values():
                    if isinstance(v, list):
                        tx_list = v
                        break
            if not tx_list:
                tx_list = []
        else:
            tx_list = []
        if not isinstance(tx_list, list) or not tx_list:
            return Response({'error': 'No transactions found in payload.'}, status=400)
        created = 0
        skipped = 0
        errors = []
        from .models import UserCompany, Company
        with db_transaction.atomic():
            for idx, tx in enumerate(tx_list):
                party_name = tx.get('party_name') or tx.get('client_name') or 'Unknown'
                voucher_no = tx.get('voucher_no') or tx.get('voucher_number') or f'V{idx+1}'
                voucher_type = (tx.get('voucher_type') or tx.get('register_type') or 'journal').lower()
                date_str = tx.get('date', '')
                narration = tx.get('narration', '')
                amount = tx.get('amount', None)
                ledger_entries = tx.get('ledger_entries') or tx.get('entries') or []
                # Parse date
                date_obj = None
                try:
                    if date_str and len(date_str) == 8 and date_str.isdigit():
                        date_obj = datetime.strptime(date_str, '%Y%m%d').date()
                    elif date_str and '/' in date_str:
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
                    elif date_str:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    else:
                        date_obj = datetime.now().date()
                except Exception:
                    date_obj = datetime.now().date()
                # Map voucher_type to register_type with comprehensive Tally voucher types
                voucher_type = str(voucher_type).lower().strip()
                register_type_map = {
                    # Main transaction types
                    'sales': 'sales',
                    'sale': 'sales',
                    'purchase': 'purchase',
                    'payment': 'payment',
                    'pay': 'payment',
                    'receipt': 'receipt',
                    'rcpt': 'receipt',
                    'journal': 'journal',
                    'jrnl': 'journal',
                    
                    # Notes and adjustments
                    'credit note': 'credit_note',
                    'debit note': 'debit_note',
                    'cnote': 'credit_note',
                    'dnote': 'debit_note',
                    
                    # Stock related
                    'stock journal': 'stock_journal',
                    'physical stock': 'physical_stock',
                    'stock transfer': 'stock_transfer',
                    'stock item transfer': 'stock_transfer',
                    
                    # Manufacturing related
                    'manufacturing journal': 'manufacturing_journal',
                    'job work out order': 'jobwork_out',
                    'job work in order': 'jobwork_in',
                    
                    # Payroll related
                    'payroll': 'payroll',
                    'attendance': 'attendance',
                    
                    # Other common types
                    'contra': 'contra',
                    'reversing journal': 'reversing_journal',
                    'memorandum': 'memorandum',
                    'optional': 'optional',
                    
                    # Opening balance and adjustment entries
                    'opening balance': 'opening_balance',
                    'balance sheet': 'balance_sheet',
                    'profit & loss': 'profit_loss',
                    
                    # Bank related
                    'bank allocation': 'bank_allocation',
                    'bank reconciliation': 'bank_reconciliation',
                    
                    # Order related
                    'purchase order': 'purchase_order',
                    'sales order': 'sales_order',
                    'rejection out': 'rejection_out',
                    'rejection in': 'rejection_in'
                }
                register_type = register_type_map.get(voucher_type, 'journal')
                logger.info(f"Mapped voucher_type '{voucher_type}' to register_type '{register_type}'")
                # Enhanced party and amount extraction for all transaction types
                party_ledger = None
                if register_type in ['receipt', 'payment', 'sales', 'purchase', 'credit_note', 'debit_note']:
                    # First try to find party ledger
                    for le in ledger_entries:
                        is_party = False
                        all_fields = le.get('all_fields', {})
                        if all_fields:
                            is_party = all_fields.get('ISPARTYLEDGER') in [True, 'Yes', 'yes', 'YES', '1', 1]
                        if is_party or le.get('is_party_ledger', False):
                            party_ledger = le
                            break
                        # Additional check for sales/purchase ledgers
                        ledger_name = le.get('ledger_name', '').lower()
                        if any(term in ledger_name for term in ['sundry debtors', 'sundry creditors', 'debtor', 'creditor']):
                            party_ledger = le
                            break
                    
                    if party_ledger:
                        try:
                            amount = abs(float(party_ledger.get('amount', 0.0) or 0.0))  # Use absolute value
                            if register_type in ['payment', 'purchase', 'debit_note']:
                                amount = -amount  # Make negative for outgoing transactions
                        except Exception as e:
                            logger.error(f"Error processing amount for {register_type}: {str(e)}")
                            amount = 0.0
                        original_party = party_name  # Store original party name
                        party_name = party_ledger.get('ledger_name', party_name)
                        if party_name == 'Unknown' and original_party != 'Unknown':
                            party_name = original_party
                    else:
                        try:
                            # Sum all non-zero amounts if no party ledger found
                            amounts = [float(le.get('amount', 0.0) or 0.0) for le in ledger_entries if le.get('amount')]
                            amount = sum(amounts) if amounts else 0.0
                        except Exception as e:
                            logger.error(f"Error summing ledger amounts: {str(e)}")
                            amount = 0.0
                else:
                    if amount in [None, '', ' ']:
                        try:
                            amount = sum(float(le.get('amount', 0.0) or 0.0) for le in ledger_entries)
                        except Exception:
                            amount = 0.0
                    else:
                        try:
                            amount = float(amount)
                        except Exception:
                            amount = 0.0
                
                # Use the company from the authenticated user
                if not company:
                    skipped += 1
                    errors.append({'idx': idx, 'reason': 'Company not available for user', 'tx': tx})
                    continue

                # Check for duplicate transaction with more specific criteria
                duplicate = TallyTransaction.objects.filter(
                    voucher_number=voucher_no,
                    register_type=register_type,
                    date=date_obj,
                    party_name=party_name,
                    amount=amount,
                    company=company
                ).first()
                
                if duplicate:
                    logger.info(f'Skipping duplicate transaction - Voucher: {voucher_no}, Type: {register_type}, Date: {date_obj}, Party: {party_name}, Company: {company.name}')
                    skipped += 1
                    errors.append({
                        'idx': idx, 
                        'reason': f'Duplicate transaction (voucher {voucher_no}, type {register_type}, date {date_obj}, party {party_name} already exists for company {company.name})', 
                        'tx': tx
                    })
                    continue
                    
                try:
                    # Create new transaction with enhanced details
                    transaction_data = {
                        'voucher_number': voucher_no,
                        'voucher_type': tx.get('voucher_type', 'Unknown'),
                        'date': date_obj,
                        'party_name': party_name,
                        'amount': amount,
                        'remaining_amount': amount,  # Initialize remaining amount
                        'register_type': register_type,
                        'company': company,
                        'is_reconciled': False  # Initialize as unreconciled
                    }
                    
                    if party_ledger:
                        transaction_data.update({
                            'party_type': 'debtor' if register_type in ['sales', 'receipt'] else 'creditor',
                            'party_ledger_name': party_ledger.get('ledger_name', ''),
                            'party_group': party_ledger.get('group_name', '')
                        })
                    
                    t = TallyTransaction.objects.create(**transaction_data)
                    for le_idx, le in enumerate(ledger_entries):
                        le_amount = le.get('amount', 0.0)
                        try:
                            le_amount = float(le_amount)
                        except Exception:
                            le_amount = 0.0
                        
                        # Determine if it's debit or credit based on the type
                        is_debit = le.get('type', '').lower() == 'debit'
                        is_credit = le.get('type', '').lower() == 'credit'
                        
                        # If type is not specified, assume credit for positive amounts
                        if not is_debit and not is_credit:
                            is_credit = True
                            is_debit = False
                        
                        LedgerEntry.objects.create(
                            transaction=t,
                            ledger_name=le.get('ledger_name', f'Unknown_{le_idx+1}'),
                            amount=le_amount,
                            is_debit=is_debit,
                            is_credit=is_credit
                        )
                    created += 1
                except Exception as e:
                    skipped += 1
                    errors.append({'idx': idx, 'reason': str(e), 'tx': tx})
        # After successful import, trigger payment pattern analysis
        try:
            from transactions.payment_analysis import PaymentPatternAnalyzer
            analyzer = PaymentPatternAnalyzer(company.id)
            analyzer.analyze_payment_patterns()
            logger.info("Payment patterns analyzed successfully")
        except Exception as e:
            logger.error(f"Error analyzing payment patterns: {str(e)}")
            logger.exception("Detailed error traceback:")  # Add detailed error logging

        return Response({
            'message': 'Transactions processed successfully',
            'transactions_created': created,
            'transactions_skipped': skipped,
            'errors': errors
        }, status=201)
