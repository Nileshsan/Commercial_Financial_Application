from django.http import JsonResponse
from django.core.cache import cache
from django.db.utils import OperationalError
import logging
import hashlib

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('transactions.data_processor')


class DBOperationalErrorMiddleware:
    """Middleware that detects DB OperationalError (e.g. MySQL code 1226)
    and returns a short 503 response while setting a short cooldown in cache.

    This prevents deep stack traces and repeated heavy attempts when the
    remote DB has exhausted per-user connection limits.
    """

    COOLDOWN_KEY = 'db_overloaded'
    COOLDOWN_SECONDS = 600  # 10 minutes

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # If a recent overload was detected, return a quick 503
        if cache.get(self.COOLDOWN_KEY):
            return JsonResponse({'detail': 'Database overloaded, try again later'}, status=503)

        try:
            return self.get_response(request)
        except OperationalError as exc:
            # Detect MySQL-specific 'exceeded' errors or code 1226
            msg = str(exc)
            is_overload = False

            # exc.args can be (errno, "message") for DB errors
            try:
                if exc.args and isinstance(exc.args[0], int) and exc.args[0] == 1226:
                    is_overload = True
                elif exc.args and isinstance(exc.args[0], tuple) and exc.args[0][0] == 1226:
                    is_overload = True
            except Exception:
                pass

            if 'exceeded' in msg.lower() or is_overload:
                logger.error('DB overload detected by middleware: %s', msg)
                try:
                    cache.set(self.COOLDOWN_KEY, True, self.COOLDOWN_SECONDS)
                except Exception:
                    # Cache best-effort; don't fail the request handling because cache is down
                    logger.debug('Failed to set db_overloaded cache key')
                return JsonResponse({'detail': 'Database overloaded, please retry later'}, status=503)

            # Not an overload we handle, re-raise
            raise



class IdempotencyMiddleware(MiddlewareMixin):
    """Simple idempotency middleware for POST /api/transactions/ endpoints.

    Behavior:
    - If request is POST to /api/transactions/ (or startswith), compute an idempotency key.
      Prefer the client-supplied 'Idempotency-Key' header; otherwise fall back to a hash
      of the path+body+auth header.
    - If the key was seen recently (cache), return 202 Accepted with a short message.
    - Otherwise store the key in cache for a TTL and allow request to proceed.

    This is a lightweight guard to avoid duplicate payload processing when clients
    retry or when network flakiness causes duplicate sends.
    """

    CACHE_PREFIX = 'idem:'
    TTL = 60 * 60  # 1 hour

    def process_request(self, request):
        # Only guard POSTs
        if request.method != 'POST':
            return None

        path = request.path or ''
        # Limit to transactions endpoint (common path used by importer)
        if not path.startswith('/api/transactions'):
            return None

        # Prefer explicit header
        idem_key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY')
        if not idem_key:
            # Fallback: hash path + body + auth header
            try:
                body = request.body or b''
            except Exception:
                body = b''
            auth = request.headers.get('Authorization', '')
            raw = path.encode('utf-8') + b'|' + body + b'|' + auth.encode('utf-8')
            idem_key = hashlib.sha256(raw).hexdigest()

        cache_key = f"{self.CACHE_PREFIX}{idem_key}"
        seen = cache.get(cache_key)
        # Diagnostics: increment a short-lived counter to see how often a given key is sent
        try:
            counter_key = cache_key + ':count'
            current = cache.get(counter_key) or 0
            cache.set(counter_key, int(current) + 1, 60 * 60)
        except Exception:
            logger.debug('Failed to increment idempotency counter')
        if seen:
            # Duplicate — return 202 Accepted (already queued/processed)
            return JsonResponse({'detail': 'Duplicate request detected — ignored'}, status=202)

        # Mark as seen
        try:
            cache.set(cache_key, True, self.TTL)
            # Also store metadata for diagnostics (ip and last-seen timestamp)
            try:
                ip = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                meta_key = cache_key + ':meta'
                cache.set(meta_key, {'ip': ip, 'path': path}, self.TTL)
            except Exception:
                logger.debug('Failed to set idempotency meta')
        except Exception:
            # best-effort
            logging.getLogger('core.middleware').debug('Failed to set idempotency cache key')

        return None
