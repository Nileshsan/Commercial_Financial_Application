from rest_framework import authentication
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication
from .models import Company

from django.db import connection
from functools import wraps
import time

def retry_on_db_error(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        raise
                    time.sleep(delay)
                    # Close the connection to force a new one
                    connection.close()
            return None
        return wrapper
    return decorator

class TokenHeaderAuthentication(TokenAuthentication):
    keyword = 'Token'
    
    @retry_on_db_error(max_retries=3, delay=1)
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Token '):
            return None
            
        token_key = auth_header.split(' ')[1] if len(auth_header.split(' ')) > 1 else None
        
        if not token_key:
            return None
            
        try:
            from rest_framework.authtoken.models import Token
            # Include company information in the query
            token = Token.objects.select_related('user', 'user__company').get(key=token_key)
            if token.user.is_active:
                # Store company in the request for easy access
                request.company = token.user.company
                return (token.user, token)
        except Token.DoesNotExist:
            return None
        except Exception as e:
            connection.close()  # Close the connection on error
            return None
        
        return None

class CompanyAPIKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY') or request.query_params.get('api_key')
        
        if not api_key:
            return None  # Let other authentication methods handle this
            
        try:
            company = Company.objects.select_related('user_company').get(api_key=api_key)
            # You can create an anonymous user object here if needed
            # or return None as the user if you're using other auth methods
            return (None, company)
        except Company.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API key')

class BearerTokenAuthentication(authentication.BaseAuthentication):
    """
    Authentication class to handle Bearer tokens from sync agent
    Extracts company information from the API key in Bearer format
    """
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
            
        api_key = auth_header.split(' ')[1] if len(auth_header.split(' ')) > 1 else None
        
        if not api_key:
            return None
            
        try:
            # Find company by API key
            company = Company.objects.select_related('user_company').get(api_key=api_key)
            # Return a tuple of (user, auth) - user can be None for API key auth
            return (None, company)
        except Company.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API key')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Authentication error: {str(e)}')
