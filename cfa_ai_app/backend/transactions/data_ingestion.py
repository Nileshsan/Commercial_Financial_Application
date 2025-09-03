from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ingest_tally_data(request):
    """Ingest data from Tally sync agent"""
    try:
        data = request.data
        data_type = data.get('type')
        company_id = request.user.company_id
        
        if not data_type:
            return Response({
                'status': 'error',
                'message': 'Data type not specified'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process the data based on type
        if data_type == 'vouchers':
            # Process vouchers
            process_vouchers(data.get('vouchers', []), company_id)
        elif data_type == 'opening_balances':
            # Process opening balances
            process_opening_balances(data.get('balances', []), company_id)
        
        # After successful data ingestion, normalize transactions and analyze patterns
        try:
            # Step 1: Normalize transactions
            from .data_processor import normalize_transactions
            normalize_transactions(company_id)
            
            # Step 2: Calculate payment patterns
            from .payment_analysis import PaymentPatternAnalyzer
            # Scope analysis to recent data by default to keep imports fast
            since_date = timezone.now().date() - timezone.timedelta(days=30)
            analyzer = PaymentPatternAnalyzer(company_id, since_date=since_date)
            patterns = analyzer.analyze_payment_patterns()
            
            message = (
                'Data processed successfully. '
                f'Found {len(patterns) if patterns else 0} payment patterns.'
            )
            
            return Response({
                'status': 'success',
                'message': message,
                'data': {
                    'patterns_count': len(patterns) if patterns else 0
                }
            })
        except Exception as e:
            logger.error(f"Error in post-processing: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Data ingested but post-processing failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from decimal import Decimal
from django.db import transaction
from .models import LedgerEntry, LedgerMaster
from accounts.models import RawTallyTransaction
from transactions.data_processor import normalize_raw_transactions

def process_vouchers(vouchers, company_id):
    """Process voucher data from Tally"""
    logger.info(f"Processing {len(vouchers)} vouchers for company {company_id}")
    
    try:
        with transaction.atomic():
            for voucher_data in vouchers:
                # Extract basic voucher information
                voucher_type = voucher_data.get('VOUCHERTYPENAME', '').lower()
                register_type = map_voucher_type_to_register(voucher_type)
                
                # Store raw voucher (append-only), normalization will convert to TallyTransaction
                RawTallyTransaction.objects.create(
                    company_id=company_id,
                    voucher_type=voucher_type,
                    voucher_number=voucher_data.get('VOUCHERNUMBER', ''),
                    date=parse_tally_date(voucher_data.get('DATE', '')),
                    amount=Decimal(str(voucher_data.get('AMOUNT', 0))),
                    party_name=voucher_data.get('PARTYNAME', '').strip(),
                    register_type=register_type,
                    remaining_amount=Decimal(str(voucher_data.get('AMOUNT', 0))),
                    raw_payload=voucher_data
                )
                
                # Process ledger entries
                ledger_entries = voucher_data.get('ALLLEDGERENTRIES', [])
                if isinstance(ledger_entries, dict):
                    ledger_entries = [ledger_entries]
                
                # Ledger entries stored inside raw_payload; normalization step may extract as needed
        
        logger.info(f"Successfully saved {len(vouchers)} raw vouchers")

        # Trigger normalization of raw rows into TallyTransaction (idempotent)
        try:
            normalize_raw_transactions(company_id)
        except Exception as e:
            logger.error(f"Normalization failed after ingesting vouchers: {e}")
            raise

        return True
        
    except Exception as e:
        logger.error(f"Error processing vouchers: {str(e)}")
        raise

def process_opening_balances(balances, company_id):
    """Process opening balance data from Tally"""
    logger.info(f"Processing opening balances for company {company_id}")
    
    try:
        with transaction.atomic():
            for balance_data in balances:
                ledger_name = balance_data.get('LEDGERNAME', '').strip()
                if not ledger_name:
                    continue
                
                # Create or update ledger master
                LedgerMaster.objects.update_or_create(
                    company_id=company_id,
                    name=ledger_name,
                    defaults={
                        'group': balance_data.get('PARENT', ''),
                        'opening_balance': Decimal(str(balance_data.get('OPENINGBALANCE', 0))),
                        'closing_balance': Decimal(str(balance_data.get('CLOSINGBALANCE', 0))),
                        'type': determine_ledger_type(balance_data)
                    }
                )
                
                # Store opening balance as raw row; normalization will convert to TallyTransaction
                opening_balance = Decimal(str(balance_data.get('OPENINGBALANCE', 0)))
                if opening_balance != 0:
                    RawTallyTransaction.objects.create(
                        company_id=company_id,
                        voucher_type='Opening Balance',
                        voucher_number=f'OB-{ledger_name}',
                        date=parse_tally_date(balance_data.get('DATE', '')),
                        amount=abs(opening_balance),
                        party_name=ledger_name,
                        register_type='opening_balance',
                        remaining_amount=abs(opening_balance),
                        raw_payload=balance_data
                    )
        
        logger.info(f"Successfully saved {len(balances)} raw opening balances")

        # Trigger normalization
        try:
            normalize_raw_transactions(company_id)
        except Exception as e:
            logger.error(f"Normalization failed after ingesting opening balances: {e}")
            raise

        return True
        
    except Exception as e:
        logger.error(f"Error processing opening balances: {str(e)}")
        raise

def map_voucher_type_to_register(voucher_type):
    """Map Tally voucher types to register types"""
    type_mapping = {
        'sales': 'sales',
        'receipt': 'receipt',
        'payment': 'payment',
        'purchase': 'purchase',
        'contra': 'contra',
        'journal': 'journal',
        'debit note': 'debit_note',
        'credit note': 'credit_note',
    }
    return type_mapping.get(voucher_type.lower(), 'other')

def determine_ledger_type(balance_data):
    """Determine ledger type based on balance data"""
    group = balance_data.get('PARENT', '').lower()
    if 'sundry debtors' in group:
        return 'debtor'
    elif 'sundry creditors' in group:
        return 'creditor'
    elif 'bank accounts' in group:
        return 'bank'
    elif 'cash in hand' in group:
        return 'cash'
    return 'other'

def parse_tally_date(date_str):
    """Parse Tally date format to Python date"""
    from datetime import datetime
    try:
        return datetime.strptime(date_str, '%Y%m%d').date()
    except:
        return timezone.now().date()
