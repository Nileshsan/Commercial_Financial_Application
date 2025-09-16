from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from django.conf import settings
import logging
from .models import TallyTransaction

logger = logging.getLogger(__name__)

# Debounce window in seconds to batch quick successive saves
DEBOUNCE_SECONDS = getattr(settings, 'TRANSACTION_DEBOUNCE_SECONDS', 10)

@receiver(post_save, sender=TallyTransaction)
def schedule_normalize_on_save(sender, instance, created, **kwargs):
    try:
        company_id = instance.company_id
        cache_key = f'normalize_debounce_{company_id}'
        lock_key = f'normalize_lock_{company_id}'
        # If there's an active normalization lock, skip scheduling to avoid adding load
        if cache.get(lock_key):
            logger.info(f"normalize signal: normalization lock active for company {company_id}, skipping schedule")
            return
        # If key exists, skip scheduling (will be handled by existing scheduled task)
        if cache.get(cache_key):
            return
        # Set key with debounce window
        cache.set(cache_key, True, timeout=DEBOUNCE_SECONDS)
        # Schedule the celery task (or fallback) to run after debounce window
        try:
            from .tasks import normalize_and_analyze
            normalize_and_analyze.apply_async((company_id,), countdown=DEBOUNCE_SECONDS)
            logger.info(f"Scheduled normalize_and_analyze for company {company_id} in {DEBOUNCE_SECONDS}s")
        except Exception as e:
            # Fallback: run the optimized normalize_transactions in a background thread
            import threading
            from .data_processor import normalize_transactions as _normalize

            def _run():
                try:
                    _normalize(company_id)
                except Exception as ex:
                    logger.error(f"Fallback normalization failed: {ex}")

            t = threading.Thread(target=_run, daemon=True)
            t.start()
    except Exception as e:
        logger.exception(f"Error in schedule_normalize_on_save: {e}")
