from django.db import transaction
from django.utils import timezone
from django.db import OperationalError
import time
from decimal import Decimal
from .models import TallyTransaction, TransactionMatching
import logging

logger = logging.getLogger(__name__)

def normalize_transactions(company_id):
    """Normalize transaction data after sync to match test data structure"""
    
    # Get all unprocessed transactions
    transactions = TallyTransaction.objects.filter(
        company_id=company_id,
        is_reconciled=False
    )
    
    # Group by party
    party_transactions = {}
    for tx in transactions:
        party_name = tx.party_name.strip()
        if not party_name:
            continue
            
        if party_name not in party_transactions:
            party_transactions[party_name] = {
                'sales': [],
                'receipts': []
            }
            
        # Normalize register type
        reg_type = tx.register_type.lower().strip()
        if reg_type in ['sales', 'sale']:
            tx.register_type = 'sales'
            party_transactions[party_name]['sales'].append(tx)
        elif reg_type in ['opening_balance']:
            # Treat opening balances as sales/outstanding so receipts can offset them
            # Keep original register_type but include in sales matching
            party_transactions[party_name]['sales'].append(tx)
        elif reg_type in ['receipt', 'rcpt', 'receipts']:
            tx.register_type = 'receipt'
            party_transactions[party_name]['receipts'].append(tx)
            
        # Ensure amount is positive
        if tx.amount < 0:
            tx.amount = abs(tx.amount)
        if not tx.remaining_amount:
            tx.remaining_amount = tx.amount

        # Save with a small retry/backoff to handle transient DB lock wait timeouts.
        # Use a savepoint (inner atomic) so that if a retry exhausts, we don't leave
        # the outer transaction in a broken state.
        save_attempts = 3
        for attempt in range(save_attempts):
            try:
                with transaction.atomic():
                    tx.save()
                break
            except OperationalError as e:
                msg = str(e)
                if 'Lock wait timeout' in msg or 'Deadlock found' in msg:
                    wait = 0.5 * (attempt + 1)
                    logger.warning(f"Transient DB lock on saving transaction {tx.id}, retrying in {wait}s (attempt {attempt+1}/{save_attempts})")
                    time.sleep(wait)
                    # rollback of the inner atomic happens automatically; retry
                    continue
                # Non-transient DB error, re-raise
                raise
        else:
            logger.error(f"Failed to save transaction {tx.id} after {save_attempts} attempts due to DB lock")
        
    # Match transactions using FIFO
    for party_name, data in party_transactions.items():
        sales = sorted(data['sales'], key=lambda x: x.date)
        receipts = sorted(data['receipts'], key=lambda x: x.date)
        
        for sale in sales:
            # Use Decimal arithmetic to avoid float rounding issues
            remaining_sale = Decimal(sale.remaining_amount or sale.amount)
            if remaining_sale <= Decimal('0'):
                continue

            for receipt in receipts:
                # Allow matching receipts regardless of whether their date is before
                # or after the sale date. Earlier receipts should offset later sales
                # (and vice-versa) so we don't skip when receipt.date < sale.date.
                remaining_receipt = Decimal(receipt.remaining_amount or receipt.amount)
                if remaining_receipt <= Decimal('0'):
                    continue

                # Match amounts using Decimal
                match_amount = remaining_sale if remaining_sale <= remaining_receipt else remaining_receipt
                if match_amount <= Decimal('0'):
                    continue
                    
                # We'll attempt to create/update the TransactionMatching inside a
                # savepoint so transient locks don't break the outer transaction.
                delay_days = (receipt.date - sale.date).days
                existing = TransactionMatching.objects.filter(
                    source_transaction=sale,
                    target_transaction=receipt
                ).first()

                match_attempts = 3
                matched = False
                for ma in range(match_attempts):
                    try:
                        with transaction.atomic():
                            if existing:
                                existing.matched_amount = Decimal(str(match_amount))
                                existing.save()
                            else:
                                TransactionMatching.objects.create(
                                    source_transaction=sale,
                                    target_transaction=receipt,
                                    matched_amount=Decimal(str(match_amount)),
                                    delay_days=delay_days
                                )
                        matched = True
                        break
                    except OperationalError as oe:
                        msg = str(oe)
                        if 'Lock wait timeout' in msg or 'Deadlock found' in msg:
                            wait = 0.5 * (ma + 1)
                            logger.warning(f"Transient DB lock when creating match for sale {sale.id} and receipt {receipt.id}, retrying in {wait}s (attempt {ma+1}/{match_attempts})")
                            time.sleep(wait)
                            continue
                        raise

                if not matched:
                    logger.error(f"Failed to create/update match for sale {sale.id} and receipt {receipt.id} after {match_attempts} attempts")
                    # Skip this pairing if we couldn't persist the match
                    continue

                # Update remaining amounts (this must run after match persisted)
                sale.remaining_amount = (remaining_sale - match_amount)
                receipt.remaining_amount = (remaining_receipt - match_amount)

                # Update reconciliation status
                sale.is_reconciled = sale.remaining_amount <= Decimal('0')
                receipt.is_reconciled = receipt.remaining_amount <= Decimal('0')

                # Save updated transactions using inner atomic savepoints to avoid
                # corrupting any outer transaction
                for attempt2 in range(3):
                    try:
                        with transaction.atomic():
                            sale.save()
                            receipt.save()
                        break
                    except OperationalError as oe:
                        msg = str(oe)
                        if 'Lock wait timeout' in msg or 'Deadlock found' in msg:
                            wait = 0.5 * (attempt2 + 1)
                            logger.warning(f"Transient DB lock when saving updated txs for sale {sale.id} and receipt {receipt.id}, retrying in {wait}s (attempt {attempt2+1}/3)")
                            time.sleep(wait)
                            continue
                        raise

                remaining_sale = float(sale.remaining_amount)
                if remaining_sale <= 0:
                    break


def normalize_raw_transactions(company_id):
    """Convert RawTallyTransaction rows (accounts app) into transactions.TallyTransaction.
    Idempotent: uses unique (company, voucher_type, voucher_number) to skip duplicates.
    Marks RawTallyTransaction.processed = True after successful upsert.
    """
    from accounts.models import RawTallyTransaction
    from django.db import IntegrityError

    raws = RawTallyTransaction.objects.filter(company_id=company_id, processed=False).order_by('created_at')
    logger.info(f"Normalizing {raws.count()} raw transactions for company {company_id}")

    for raw in raws:
        try:
            with transaction.atomic():
                # Check for existing normalized transaction
                exists = TallyTransaction.objects.filter(
                    company_id=company_id,
                    voucher_type__iexact=raw.voucher_type,
                    voucher_number__iexact=(raw.voucher_number or '')
                ).exists()

                if exists:
                    # Already normalized; mark processed and continue
                    raw.processed = True
                    raw.save()
                    continue

                # Create normalized transaction
                tt = TallyTransaction.objects.create(
                    company_id=company_id,
                    voucher_type=raw.voucher_type,
                    voucher_number=raw.voucher_number or '',
                    date=raw.date or timezone.now().date(),
                    amount=raw.amount or Decimal('0'),
                    party_name=(raw.party_name or '').strip(),
                    register_type=(raw.register_type or '').lower(),
                    remaining_amount=(raw.remaining_amount if raw.remaining_amount is not None else raw.amount)
                )

                # Mark raw as processed
                raw.processed = True
                raw.save()
        except IntegrityError as ie:
            logger.warning(f"Integrity error while normalizing raw {raw.id}: {ie}")
            # leave raw unprocessed for retry
        except Exception as e:
            logger.error(f"Failed to normalize raw transaction {raw.id}: {e}")
            # do not mark processed so we can retry later
