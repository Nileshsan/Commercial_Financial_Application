from celery import shared_task
from .data_processor import normalize_transactions
import logging
from .payment_analysis import PaymentPatternAnalyzer
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def normalize_transactions_task(self, company_id):
    """Celery task wrapper for normalize_transactions"""
    try:
        result = normalize_transactions(company_id)
        logger.info(f"normalize_transactions_task completed: {result} matches created for company {company_id}")
        return {'matches_created': result}
    except Exception as e:
        logger.exception(f"normalize_transactions_task failed: {e}")
        raise

@shared_task(bind=True)
def analyze_payment_patterns_task(self, company_id):
    """Run payment pattern analysis after normalization finishes"""
    try:
        since_date = timezone.now().date() - timedelta(days=30)
        analyzer = PaymentPatternAnalyzer(company_id, since_date=since_date)
        patterns = analyzer.analyze_payment_patterns()
        logger.info(f"analyze_payment_patterns_task completed: {len(patterns)} patterns for company {company_id}")
        return {'patterns': len(patterns)}
    except Exception as e:
        logger.exception(f"analyze_payment_patterns_task failed: {e}")
        raise

@shared_task(bind=True)
def normalize_and_analyze(self, company_id):
    """Combine normalization and analysis in one chain for convenience"""
    res = normalize_transactions_task(company_id)
    # Trigger analysis after normalization (synchronously here to preserve order)
    analyze_payment_patterns_task(company_id)
    return res
