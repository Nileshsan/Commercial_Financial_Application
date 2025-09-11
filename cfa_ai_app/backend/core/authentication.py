from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
import jwt

User = get_user_model()

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Get the API key from headers
        api_key = request.META.get('HTTP_API_KEY')
        if not api_key or api_key != settings.API_KEY:
            raise AuthenticationFailed('Invalid API key')

        # Get the auth token from header
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None  # Allow unauthenticated access to some endpoints

        try:
            # Remove 'Bearer ' prefix
            if ' ' in auth_header:
                scheme, token = auth_header.split(' ', 1)
                if scheme.lower() != 'bearer':
                    raise AuthenticationFailed('Invalid authentication scheme')
            else:
                token = auth_header

            # Decode the JWT token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            
            if not user_id:
                raise AuthenticationFailed('Invalid token payload')

            user = User.objects.get(id=user_id)
            return (user, token)

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found')

    def authenticate_header(self, request):
        return 'Bearer'
