from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    TallyTransaction,
    BankBalance,
    PaymentPattern,
    TransactionMatching,
)


logger = logging.getLogger(__name__)


class PaymentAnalysisError(Exception):
    """Raised when payment analysis cannot proceed due to invalid or insufficient data."""


class PaymentPatternAnalyzer:
    """Analyze payment/receipt transactions to build payment patterns and make predictions.

    This class focuses on readability and defensive programming. It keeps the
    original FIFO matching behavior but centralizes queryset filtering and
    improves logging and error handling.
    """

    def __init__(
        self,
        company_id: int,
        since_date: Optional[datetime.date] = None,
        transaction_ids: Optional[List[int]] = None,
    ) -> None:
        self.company_id = company_id
        self.since_date = since_date
        self.transaction_ids = transaction_ids
        self.payment_patterns: Dict[str, Dict] = {}
        self.fixed_expenses: Dict[str, Dict] = {}

    # ------------------------ Query helpers ------------------------
    def _base_transactions(self):
        """Return a base queryset optionally scoped by `since_date` / `transaction_ids`.

        Keeping this centralized avoids accidental full-table scans.
        """
        qs = TallyTransaction.objects.filter(company_id=self.company_id)
        if self.since_date:
            qs = qs.filter(date__gte=self.since_date)
        if self.transaction_ids:
            qs = qs.filter(id__in=self.transaction_ids)
        return qs

    # ------------------------ Matching helpers ------------------------
    def _update_transaction_matching(self, sale: TallyTransaction, receipt: TallyTransaction, allocated_amount: float) -> None:
        """Create or update a TransactionMatching and update remaining amounts.

        This operation is wrapped in a DB transaction to keep the two updates
        (matching + remaining_amounts) atomic.
        """
        try:
            with transaction.atomic():
                match = TransactionMatching.objects.filter(
                    source_transaction=sale, target_transaction=receipt
                ).first()

                delay_days = (receipt.date - sale.date).days

                if match:
                    match.matched_amount = allocated_amount
                    match.delay_days = delay_days
                    match.save()
                    logger.debug("Updated existing TransactionMatching %s", match.id)
                else:
                    TransactionMatching.objects.create(
                        source_transaction=sale,
                        target_transaction=receipt,
                        matched_amount=allocated_amount,
                        delay_days=delay_days,
                    )
                    logger.debug("Created new TransactionMatching for sale=%s receipt=%s", sale.id, receipt.id)

                # Safely update remaining_amount fields
                try:
                    sale.remaining_amount = float(sale.remaining_amount or sale.amount) - allocated_amount
                except Exception:
                    sale.remaining_amount = float(sale.amount) - allocated_amount

                try:
                    receipt.remaining_amount = float(receipt.remaining_amount or receipt.amount) - allocated_amount
                except Exception:
                    receipt.remaining_amount = float(receipt.amount) - allocated_amount

                sale.is_reconciled = (sale.remaining_amount or 0) <= 0
                receipt.is_reconciled = (receipt.remaining_amount or 0) <= 0

                sale.save()
                receipt.save()
        except Exception as exc:  # pragma: no cover - bubble up after logging
            logger.exception("Failed to update transaction matching for sale=%s receipt=%s: %s", sale.id, receipt.id, exc)
            raise

    # ------------------------ Analysis functions ------------------------
    def analyze_payment_patterns(self) -> Dict[str, Dict]:
        """Main entry point to analyze payment patterns.

        Returns a mapping of party_name -> pattern metadata.
        """
        logger.info("Starting payment pattern analysis for company=%s", self.company_id)

        qs = self._base_transactions().select_related('company').order_by('party_name', 'date', 'id')

        # Collect transactions grouped by party and normalized type
        party_tx: Dict[str, Dict[str, List[TallyTransaction]]] = {}

        for tx in qs:
            party_name = (tx.party_name or '').strip()
            if not party_name:
                logger.warning("Skipping transaction %s with empty party_name", tx.id)
                continue

            reg = (tx.register_type or '').lower().strip()
            try:
                tx.amount = abs(float(tx.amount or 0))
            except Exception:
                logger.warning("Invalid amount for tx %s: %r", tx.id, tx.amount)
                tx.amount = 0.0

            bucket = party_tx.setdefault(party_name, {'sales': [], 'receipts': []})
            if reg in ('sales', 'sale'):
                bucket['sales'].append(tx)
            elif reg in ('receipt', 'receipts', 'rcpt'):
                bucket['receipts'].append(tx)

        logger.info("Collected transactions for %d parties", len(party_tx))

        # Per-party FIFO matching pass
        for party, buckets in party_tx.items():
            sales = sorted(buckets['sales'], key=lambda t: (t.date, t.id))
            receipts = sorted(buckets['receipts'], key=lambda t: (t.date, t.id))

            if not sales or not receipts:
                logger.debug("Skipping party %s - insufficient sales/receipts", party)
                continue

            payment_delays = []
            receipt_idx = 0

            for sale in sales:
                remaining_sale = float(sale.amount or 0)
                if remaining_sale <= 0:
                    continue

                while remaining_sale > 0 and receipt_idx < len(receipts):
                    receipt = receipts[receipt_idx]
                    remaining_receipt = float(receipt.remaining_amount or receipt.amount or 0)

                    # Skip receipts before the sale date
                    if receipt.date < sale.date:
                        receipt_idx += 1
                        continue

                    if remaining_receipt <= 0:
                        receipt_idx += 1
                        continue

                    allocate = min(remaining_sale, remaining_receipt)
                    if allocate > 0:
                        try:
                            self._update_transaction_matching(sale, receipt, allocate)
                            delay_days = (receipt.date - sale.date).days
                            payment_delays.append({'days': delay_days, 'amount': allocate})
                            remaining_sale -= allocate
                        except Exception:
                            logger.exception("Error matching sale %s to receipt %s", sale.id, receipt.id)

                    # Move to next receipt if fully consumed
                    if float(receipt.remaining_amount or receipt.amount or 0) <= allocate:
                        receipt_idx += 1

            # Compute weighted statistics for the party
            if not payment_delays:
                continue

            total_matched = sum(d['amount'] for d in payment_delays)
            if total_matched < 0.01:
                logger.debug("Negligible matched amount for party %s", party)
                continue

            weighted_sum = sum(d['days'] * d['amount'] for d in payment_delays)
            avg_delay = weighted_sum / total_matched

            # Compute variance/std deviation
            mean = avg_delay
            variance = sum(((d['days'] - mean) ** 2) * d['amount'] for d in payment_delays) / total_matched
            std_dev = variance ** 0.5

            sample_size = len(payment_delays)
            confidence = min(sample_size / 10.0, 1.0)

            pattern = {
                'avg_delay': int(round(avg_delay)),
                'std_deviation': float(round(std_dev, 2)),
                'sample_size': sample_size,
                'confidence': float(round(confidence, 2)),
            }

            self.payment_patterns[party] = pattern
            try:
                PaymentPattern.objects.update_or_create(
                    company_id=self.company_id,
                    party_name=party,
                    defaults={
                        'avg_payment_days': pattern['avg_delay'],
                        'confidence_score': pattern['confidence'],
                        'delay_std_deviation': pattern['std_deviation'],
                        'pattern_consistency': pattern['confidence'],
                        'sample_size': pattern['sample_size'],
                        'last_analysis_date': timezone.now().date(),
                    },
                )
            except Exception:
                logger.exception("Failed to persist PaymentPattern for party %s", party)

        # Second pass using DataFrame for parties where it helps compute weighted averages
        try:
            sales_qs = self._base_transactions().filter(register_type__in=['sales', 'sale']).order_by('date', 'id')
            receipts_qs = self._base_transactions().filter(register_type__in=['receipt', 'receipts', 'rcpt']).order_by('date', 'id')

            sales_vals = list(sales_qs.values())
            receipts_vals = list(receipts_qs.values())

            if not sales_vals or not receipts_vals:
                logger.debug("Not enough data for DataFrame second-pass analysis")
                return self.payment_patterns

            sales_df = pd.DataFrame(sales_vals)
            receipts_df = pd.DataFrame(receipts_vals)

            if 'party_name' in sales_df.columns:
                for party in sales_df['party_name'].dropna().unique():
                    s_rows = sales_df[sales_df['party_name'] == party]
                    r_rows = receipts_df[receipts_df['party_name'] == party]
                    if s_rows.empty or r_rows.empty:
                        continue

                    delays: List[int] = []
                    weights: List[float] = []
                    receipt_amounts: Dict[int, float] = {}

                    for _, s in s_rows.iterrows():
                        sale_amount = float(s.get('amount', 0) or 0)
                        sale_date = pd.to_datetime(s.get('date')).date()
                        remaining_sale = sale_amount
                        try:
                            sale_obj = TallyTransaction.objects.get(id=s['id'])
                        except TallyTransaction.DoesNotExist:
                            continue

                        # iterate receipts that are on/after the sale
                        for _, r in r_rows[r_rows['date'] >= s.get('date')].iterrows():
                            if remaining_sale <= 0:
                                break
                            rid = int(r['id'])
                            try:
                                if rid not in receipt_amounts:
                                    r_obj = TallyTransaction.objects.get(id=rid)
                                    receipt_amounts[rid] = float(r_obj.remaining_amount or r_obj.amount or 0)
                                alloc = min(remaining_sale, receipt_amounts[rid])
                                if alloc <= 0:
                                    continue
                                receipt_amounts[rid] -= alloc
                                remaining_sale -= alloc
                                delays.append(int((pd.to_datetime(r['date']).date() - sale_date).days))
                                weights.append(alloc)
                                self._update_transaction_matching(sale_obj, TallyTransaction.objects.get(id=rid), alloc)
                            except Exception:
                                logger.exception("Error during DataFrame pass matching for party %s", party)

                    if delays:
                        weighted_avg = float(np.average(delays, weights=weights)) if weights else float(np.mean(delays))
                        confidence = min(len(delays) / 10.0, 1.0)
                        std = float(np.std(delays)) if len(delays) > 1 else 0.0
                        consistency = 1.0 / (1.0 + (std / 30.0)) if std else 1.0

                        pattern = {
                            'avg_delay': int(round(weighted_avg)),
                            'confidence': float(round(confidence * consistency, 2)),
                            'sample_size': len(delays),
                            'std_deviation': float(round(std, 2)),
                        }

                        self.payment_patterns[party] = pattern
                        try:
                            PaymentPattern.objects.update_or_create(
                                company_id=self.company_id,
                                party_name=party,
                                defaults={
                                    'avg_payment_days': pattern['avg_delay'],
                                    'confidence_score': pattern['confidence'],
                                    'delay_std_deviation': pattern['std_deviation'],
                                    'pattern_consistency': pattern['confidence'],
                                    'sample_size': pattern['sample_size'],
                                    'last_analysis_date': timezone.now().date(),
                                },
                            )
                        except Exception:
                            logger.exception("Failed to persist PaymentPattern for party %s (dataframe pass)", party)

        except Exception:
            logger.exception("Second-pass DataFrame analysis failed")

        return self.payment_patterns

    # ------------------------ Fixed expenses analysis ------------------------
    def analyze_fixed_expenses(self) -> Dict[str, Dict]:
        """Detect fixed/recurring outgoing payments for the company.

        Returns a mapping of party_name -> expense metadata.
        """
        try:
            qs = self._base_transactions().filter(register_type='payment').order_by('date')
            rows = list(qs.values())
            if not rows:
                return self.fixed_expenses

            df = pd.DataFrame(rows)
            if 'party_name' not in df.columns or 'date' not in df.columns:
                return self.fixed_expenses

            for party in df['party_name'].dropna().unique():
                part = df[df['party_name'] == party]
                if len(part) < 3:
                    continue

                amounts = part['amount'].astype(float).tolist()
                dates = [pd.to_datetime(d).date() for d in part['date'].tolist()]

                intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
                avg_interval = float(np.mean(intervals))
                std_interval = float(np.std(intervals))
                avg_amount = float(np.mean(amounts))
                std_amount = float(np.std(amounts))

                if std_interval < avg_interval * 0.2 and std_amount < avg_amount * 0.1:
                    self.fixed_expenses[party] = {
                        'amount': round(avg_amount, 2),
                        'interval_days': int(round(avg_interval)),
                        'confidence': float(min(len(dates) / 12.0, 1.0)),
                        'last_paid_date': dates[-1].isoformat(),
                    }

            return self.fixed_expenses
        except Exception:
            logger.exception("Failed to analyze fixed expenses for company=%s", self.company_id)
            return self.fixed_expenses

    # ------------------------ Predictions ------------------------
    def predict_future_payments(self, days: int = 90) -> List[Dict]:
        """Produce a list of predicted cashflow items (receipts/payments/balance).

        Returned items are dictionaries with keys: date, amount, type, party, probability, (optional)is_estimated
        """
        current_date = timezone.now().date()
        end_date = current_date + timedelta(days=days)
        predicted: List[Dict] = []

        bank_balance = self.get_current_bank_balance()
        predicted.append(
            {
                'date': current_date.isoformat(),
                'amount': float(bank_balance),
                'type': 'balance',
                'party': 'Bank',
                'probability': 1.0,
                'is_estimated': bank_balance == 0,
            }
        )

        # Outstanding sales (simple heuristic)
        outstanding_sales = (
            self._base_transactions()
            .filter(register_type__in=['sales', 'sale'])
            .exclude(
                party_name__in=self._base_transactions()
                .filter(register_type__in=['receipt', 'receipts', 'rcpt'], date__lte=current_date)
                .values_list('party_name', flat=True)
            )
            .values('date', 'amount', 'party_name')
        )

        for sale in outstanding_sales:
            party = sale.get('party_name')
            if not party:
                continue
            pattern = self.payment_patterns.get(party)
            if not pattern:
                continue
            predicted_date = pd.to_datetime(sale['date']).date() + timedelta(days=int(pattern['avg_delay']))
            if predicted_date <= end_date:
                predicted.append(
                    {
                        'date': predicted_date.isoformat(),
                        'amount': float(sale.get('amount', 0) or 0),
                        'type': 'receipt',
                        'party': party,
                        'probability': pattern.get('confidence', 0.0),
                    }
                )

        # Add fixed expenses
        for party, exp in self.fixed_expenses.items():
            try:
                last = datetime.strptime(exp.get('last_paid_date', ''), '%Y-%m-%d').date()
            except Exception:
                continue
            interval = int(exp['interval_days'])
            next_date = last + timedelta(days=interval)
            while next_date <= end_date:
                predicted.append(
                    {
                        'date': next_date.isoformat(),
                        'amount': -float(exp['amount']),
                        'type': 'payment',
                        'party': party,
                        'probability': exp.get('confidence', 0.5),
                    }
                )
                next_date += timedelta(days=interval)

        return sorted(predicted, key=lambda d: d['date'])

    # ------------------------ Bank balance helper ------------------------
    def get_current_bank_balance(self) -> float:
        """Return latest bank balance or compute from transactions if missing."""
        try:
            latest = BankBalance.objects.filter(company_id=self.company_id).order_by('-updated_at').first()
            if latest:
                return float(latest.balance)

            total = 0.0
            for t in self._base_transactions().filter(date__lte=timezone.now()):
                if (t.register_type or '').lower().strip() in ('receipt',):
                    total += float(t.amount or 0)
                elif (t.register_type or '').lower().strip() in ('payment',):
                    total -= float(t.amount or 0)

            # Persist a simple snapshot
            try:
                BankBalance.objects.create(company_id=self.company_id, balance=total, account_name='default')
            except Exception:
                logger.debug("Could not create BankBalance snapshot for company=%s", self.company_id)

            return total
        except Exception:
            logger.exception("Failed to compute bank balance for company=%s", self.company_id)
            return 0.0

