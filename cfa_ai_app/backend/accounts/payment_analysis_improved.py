from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models, transaction
from django.db.models import (
    Avg, F, Q, ExpressionWrapper, DurationField, Sum, Count, Max,
    Window, Value, Case, When, OuterRef, Subquery
)
from django.utils import timezone
from django.db.models.functions import Lag, ExtractMonth, Cast, Coalesce
from django.core.cache import cache
from django.conf import settings
from transactions.models import (
    TallyTransaction, BankBalance, PaymentPattern, TransactionMatching, PartyBalance,
    FixedExpense
)
from .models import LedgerOpeningBalance
import numpy as np
import pandas as pd
import json
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class PaymentPatternAnalyzer:
    CACHE_KEY_PREFIX = 'payment_pattern_'
    CACHE_TIMEOUT = 3600  # 1 hour cache

    def __init__(self, company_id):
        """Initialize the analyzer with caching and validation"""
        if not company_id:
            raise ValueError("Company ID is required")
            
        self.company_id = company_id
        self.payment_patterns = {}
        self.fixed_expenses = {}
        self.unpaid_sales = []
        self.cache_key = f"{self.CACHE_KEY_PREFIX}{company_id}"
        
        logger.info(f"Initializing PaymentPatternAnalyzer for company {company_id}")
        
        # Try to load cached data first
        cached_data = cache.get(self.cache_key)
        if cached_data:
            try:
                self.payment_patterns = cached_data.get('patterns', {})
                self.fixed_expenses = cached_data.get('expenses', {})
                logger.info("Loaded analyzer data from cache")
                return
            except Exception as e:
                logger.error(f"Error loading cached data: {str(e)}")
        
        # Validate company existence and data
        try:
            # Use aggregation for efficient counting
            transaction_stats = TallyTransaction.objects.filter(
                company_id=self.company_id
            ).values('register_type').annotate(
                count=Count('id')
            ).order_by()
            
            stats_dict = {stat['register_type']: stat['count'] for stat in transaction_stats}
            transaction_count = sum(stats_dict.values())
            sales_count = stats_dict.get('sales', 0)
            receipt_count = stats_dict.get('receipt', 0)
            
            logger.info(f"Data validation - Total: {transaction_count}, Sales: {sales_count}, Receipts: {receipt_count}")
            
            if transaction_count == 0:
                raise ValueError("No transaction data found. Please import your Tally data first.")
                
            # Initialize party balances and patterns
            self._ensure_party_balances()
            
            # Cache the initialized data
            self._cache_data()
            
        except Exception as e:
            logger.error(f"Error initializing analyzer: {str(e)}")
            raise ValueError(f"Error initializing payment analysis: {str(e)}")

    def _cache_data(self):
        """Cache the current state of patterns and expenses"""
        try:
            cache_data = {
                'patterns': self.payment_patterns,
                'expenses': self.fixed_expenses,
                'last_updated': timezone.now().isoformat()
            }
            cache.set(self.cache_key, cache_data, self.CACHE_TIMEOUT)
        except Exception as e:
            logger.error(f"Error caching data: {str(e)}")

    def _ensure_party_balances(self):
        """Ensure party balances exist with optimized querying"""
        try:
            # Use select_related for efficient querying
            balances = PartyBalance.objects.filter(
                company_id=self.company_id
            ).select_related()
            
            if not balances.exists():
                logger.info(f"No party balances found. Generating...")
                self._generate_party_balances()
            else:
                # Validate balances are up to date
                latest_transaction = TallyTransaction.objects.filter(
                    company_id=self.company_id
                ).order_by('-date').values('date').first()
                
                if latest_transaction:
                    latest_balance_update = balances.order_by('-last_updated').values('last_updated').first()
                    if latest_balance_update and latest_balance_update['last_updated'].date() < latest_transaction['date']:
                        logger.info("Party balances outdated. Regenerating...")
                        self._generate_party_balances()
                        
        except Exception as e:
            logger.error(f"Error ensuring party balances: {str(e)}")
            raise

    def _generate_party_balances(self):
        """Generate party balances with optimized batch processing"""
        try:
            with transaction.atomic():
                # Get unique parties with efficient querying
                parties_query = (
                    TallyTransaction.objects.filter(company_id=self.company_id)
                    .values('party_name')
                    .union(
                        LedgerOpeningBalance.objects.filter(company_id=self.company_id)
                        .values('ledger_name')
                    )
                    .distinct()
                )
                
                parties = [p['party_name'] for p in parties_query]
                
                if not parties:
                    logger.warning(f"No parties found for company {self.company_id}")
                    return 0
                
                batch_size = 100
                total_processed = 0
                
                # Process in batches for better performance
                for i in range(0, len(parties), batch_size):
                    batch_parties = parties[i:i+batch_size]
                    self._process_party_balance_batch(batch_parties)
                    total_processed += len(batch_parties)
                    logger.info(f"Processed {total_processed}/{len(parties)} parties")
                
                return total_processed
                
        except Exception as e:
            logger.error(f"Error generating party balances: {str(e)}")
            raise

    def _process_party_balance_batch(self, party_batch):
        """Process a batch of parties for balance calculation"""
        try:
            # Prefetch related data for the batch
            opening_balances = {
                b.ledger_name: b.opening_balance 
                for b in LedgerOpeningBalance.objects.filter(
                    company_id=self.company_id,
                    ledger_name__in=party_batch
                )
            }
            
            # Get aggregated transaction data
            transaction_sums = (
                TallyTransaction.objects.filter(
                    company_id=self.company_id,
                    party_name__in=party_batch
                )
                .values('party_name', 'register_type')
                .annotate(
                    total=Sum('amount'),
                    last_date=Max('date')
                )
            )
            
            # Organize transaction data by party
            party_data = defaultdict(lambda: {
                'sales': Decimal('0'),
                'receipts': Decimal('0'),
                'last_date': None
            })
            
            for t in transaction_sums:
                if t['register_type'] == 'sales':
                    party_data[t['party_name']]['sales'] = t['total']
                elif t['register_type'] == 'receipt':
                    party_data[t['party_name']]['receipts'] = t['total']
                if t['last_date']:
                    if not party_data[t['party_name']]['last_date'] or t['last_date'] > party_data[t['party_name']]['last_date']:
                        party_data[t['party_name']]['last_date'] = t['last_date']
            
            # Prepare bulk update data
            bulk_data = []
            for party_name in party_batch:
                data = party_data[party_name]
                opening_balance = opening_balances.get(party_name, Decimal('0'))
                current_balance = (
                    opening_balance + 
                    data['sales'] - 
                    data['receipts']
                )
                
                bulk_data.append(
                    PartyBalance(
                        company_id=self.company_id,
                        party_name=party_name,
                        current_balance=current_balance,
                        last_transaction_date=data['last_date'] or timezone.now().date(),
                        last_updated=timezone.now()
                    )
                )
            
            # Bulk update/create
            PartyBalance.objects.bulk_create(
                bulk_data,
                update_conflicts=True,
                unique_fields=['company_id', 'party_name'],
                update_fields=['current_balance', 'last_transaction_date', 'last_updated']
            )
            
        except Exception as e:
            logger.error(f"Error processing party balance batch: {str(e)}")
            raise

    def _update_transaction_matching(self, sale, receipt, allocated_amount):
        """Create or update transaction matching records with validation"""
        try:
            with transaction.atomic():
                if not isinstance(allocated_amount, (int, float, Decimal)):
                    raise ValueError(f"Invalid allocated amount type: {type(allocated_amount)}")
                
                allocated_amount = Decimal(str(allocated_amount))
                
                if allocated_amount <= 0:
                    raise ValueError(f"Invalid allocated amount: {allocated_amount}")
                
                matching, created = TransactionMatching.objects.get_or_create(
                    source_transaction=sale,
                    target_transaction=receipt,
                    defaults={
                        'matched_amount': allocated_amount,
                        'delay_days': (receipt.date - sale.date).days
                    }
                )
                
                if not created:
                    matching.matched_amount = allocated_amount
                    matching.save(update_fields=['matched_amount'])
                
                # Update remaining amounts
                self._update_transaction_remaining_amounts(sale, receipt, allocated_amount)
                
        except Exception as e:
            logger.error(f"Error updating transaction matching: {str(e)}")
            raise

    def _update_transaction_remaining_amounts(self, sale, receipt, allocated_amount):
        """Update remaining amounts for transactions"""
        try:
            sale.remaining_amount = Coalesce(F('remaining_amount'), F('amount')) - allocated_amount
            receipt.remaining_amount = Coalesce(F('remaining_amount'), F('amount')) - allocated_amount
            
            sale.save(update_fields=['remaining_amount'])
            receipt.save(update_fields=['remaining_amount'])
            
        except Exception as e:
            logger.error(f"Error updating remaining amounts: {str(e)}")
            raise

    def _save_payment_pattern(self, party_name: str, pattern_data: Dict[str, Any]):
        """Save or update payment pattern with validation and error handling"""
        try:
            if not self.company_id:
                raise ValueError("company_id is not set")
            
            if not party_name:
                raise ValueError("party_name is required")
            
            # Validate and normalize pattern data
            pattern_data = self._validate_pattern_data(pattern_data)
            
            # Update cache
            self.payment_patterns[party_name] = pattern_data
            self._cache_data()
            
            # Save to database
            PaymentPattern.objects.update_or_create(
                company_id=self.company_id,
                party_name=party_name,
                defaults=self._prepare_pattern_defaults(pattern_data)
            )
            
        except Exception as e:
            logger.error(f"Error saving payment pattern for {party_name}: {str(e)}")
            raise

    def _validate_pattern_data(self, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize pattern data"""
        validated = pattern_data.copy()
        
        # Validate avg_delay
        avg_delay = pattern_data.get('avg_delay')
        if avg_delay is None or avg_delay < 0:
            validated['avg_delay'] = 30
            logger.warning(f"Invalid avg_delay: {avg_delay}, using default")
        
        # Validate confidence
        confidence = pattern_data.get('confidence', 0)
        validated['confidence'] = max(0, min(confidence, 1))
        
        # Add additional metrics
        validated.update({
            'sample_size': pattern_data.get('sample_size', 0),
            'std_deviation': pattern_data.get('std_deviation', 0),
            'last_updated': timezone.now()
        })
        
        return validated

    def _prepare_pattern_defaults(self, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare pattern data for database storage"""
        confidence = pattern_data['confidence']
        return {
            'avg_payment_days': pattern_data['avg_delay'],
            'confidence_score': confidence,
            'delay_std_deviation': pattern_data['std_deviation'],
            'pattern_consistency': confidence,
            'sample_size': pattern_data['sample_size'],
            'last_analysis_date': timezone.now().date(),
            'data_quality': 'good' if confidence > 0.7 else 'fair' if confidence > 0.4 else 'poor'
        }

    def get_bank_balance(self) -> float:
        """Get current bank balance with caching"""
        cache_key = f"bank_balance_{self.company_id}"
        cached_balance = cache.get(cache_key)
        
        if cached_balance is not None:
            return cached_balance
            
        try:
            balance = BankBalance.objects.filter(
                company_id=self.company_id
            ).order_by('-updated_at').first()
            
            if balance:
                initial_balance = float(balance.balance)
            else:
                # Calculate from transactions
                totals = (
                    TallyTransaction.objects.filter(company_id=self.company_id)
                    .values('register_type')
                    .annotate(total=Sum('amount'))
                )
                
                balance_dict = {t['register_type']: t['total'] or Decimal('0.00') for t in totals}
                initial_balance = float(
                    balance_dict.get('receipt', Decimal('0.00')) -
                    balance_dict.get('payment', Decimal('0.00'))
                )
                
                # Create balance record
                BankBalance.objects.create(
                    company_id=self.company_id,
                    balance=initial_balance,
                    account_name='default'
                )
            
            # Cache the result
            cache.set(cache_key, initial_balance, 300)  # Cache for 5 minutes
            return initial_balance
            
        except Exception as e:
            logger.error(f"Error getting bank balance: {str(e)}")
            return 0

    def get_unpaid_sales(self) -> Dict[str, Any]:
        """Get unpaid sales with optimized querying"""
        cache_key = f"unpaid_sales_{self.company_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
            
        try:
            # Get unpaid sales with efficient querying
            unpaid_sales = (
                TallyTransaction.objects.filter(
                    company_id=self.company_id,
                    register_type='sales',
                    remaining_amount__gt=0
                )
                .select_related()
                .values(
                    'id', 'party_name', 'date', 'amount',
                    'remaining_amount', 'voucher_number'
                )
                .order_by('date')
            )
            
            result = {
                'unpaid_sales': list(unpaid_sales),
                'total_unpaid': sum(sale['remaining_amount'] for sale in unpaid_sales),
                'count': len(unpaid_sales),
                'last_updated': timezone.now().isoformat()
            }
            
            # Cache for 15 minutes
            cache.set(cache_key, result, 900)
            return result
            
        except Exception as e:
            logger.error(f"Error getting unpaid sales: {str(e)}")
            raise

    def get_payment_analysis(self) -> Dict[str, Any]:
        """Get comprehensive payment analysis"""
        cache_key = f"payment_analysis_{self.company_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
            
        try:
            # Get party statistics
            party_stats = self._get_party_statistics()
            
            # Get aging analysis
            aging = self._get_aging_analysis()
            
            # Get payment trends
            trends = self._get_payment_trends()
            
            # Ensure we have valid data even if some parts fail
            result = {
                'party_statistics': party_stats or {},
                'aging_analysis': aging or {},
                'payment_trends': trends or {},
                'total_parties': len(self.payment_patterns or {}),
                'total_patterns': len([p for p in (self.payment_patterns or {}).values() if p.get('confidence', 0) > 0.5]),
                'last_updated': timezone.now().isoformat(),
                'data_available': bool(party_stats or aging or trends)
            }
            
            # Cache for 15 minutes
            cache.set(cache_key, result, 900)
            return result
            
        except Exception as e:
            logger.error(f"Error getting payment analysis: {str(e)}")
            raise

    def _get_party_statistics(self) -> Dict[str, Any]:
        """Get party-wise payment statistics"""
        try:
            party_balances = PartyBalance.objects.filter(
                company_id=self.company_id,
                current_balance__gt=0
            ).values('party_name', 'current_balance')
            
            stats = {
                'total_outstanding': sum(float(b['current_balance']) for b in party_balances),
                'party_count': len(party_balances),
                'party_details': [
                    {
                        'name': balance['party_name'],
                        'balance': float(balance['current_balance']),
                        'pattern': self.payment_patterns.get(balance['party_name'], {})
                    }
                    for balance in party_balances
                ]
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting party statistics: {str(e)}")
            return {}

    def _get_aging_analysis(self) -> Dict[str, Any]:
        """Get aging analysis of unpaid amounts"""
        try:
            today = timezone.now().date()
            
            unpaid_sales = TallyTransaction.objects.filter(
                company_id=self.company_id,
                register_type='sales',
                remaining_amount__gt=0
            )
            
            aging_buckets = {
                '0-30': 0,
                '31-60': 0,
                '61-90': 0,
                '90+': 0
            }
            
            for sale in unpaid_sales:
                days = (today - sale.date).days
                if days <= 30:
                    aging_buckets['0-30'] += float(sale.remaining_amount)
                elif days <= 60:
                    aging_buckets['31-60'] += float(sale.remaining_amount)
                elif days <= 90:
                    aging_buckets['61-90'] += float(sale.remaining_amount)
                else:
                    aging_buckets['90+'] += float(sale.remaining_amount)
            
            return aging_buckets
            
        except Exception as e:
            logger.error(f"Error getting aging analysis: {str(e)}")
            return {}

    def _get_payment_trends(self) -> Dict[str, Any]:
        """Get payment trends over time"""
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=90)
            
            receipts = (
                TallyTransaction.objects.filter(
                    company_id=self.company_id,
                    register_type='receipt',
                    date__gte=start_date
                )
                .values('date')
                .annotate(total=Sum('amount'))
                .order_by('date')
            )
            
            trends = {
                'daily_receipts': [
                    {
                        'date': receipt['date'].isoformat(),
                        'amount': float(receipt['total'])
                    }
                    for receipt in receipts
                ],
                'total_receipts': sum(float(r['total']) for r in receipts)
            }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting payment trends: {str(e)}")
            return {}
