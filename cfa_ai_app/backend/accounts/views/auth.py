from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging

logger = logging.getLogger('django')
User = get_user_model()

def add_cors_headers(response):
    """Add CORS headers to response"""
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response["Access-Control-Max-Age"] = "86400"  # 24 hours
    return response

@csrf_exempt
@api_view(['POST', 'OPTIONS'])
@permission_classes([AllowAny])
@authentication_classes([])
def login_view(request):
    """Handle login requests with both username and email support"""
    
    logger.info("=== Login Request ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"Headers: {request.headers}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"Body: {request.body}")
    
    if request.method == 'OPTIONS':
        return add_cors_headers(Response(status=status.HTTP_200_OK))

    username = request.data.get('username') or request.data.get('email', '')
    password = request.data.get('password', '')

    if not username or not password:
        response = Response({
            'error': 'Please provide both username/email and password'
        }, status=status.HTTP_400_BAD_REQUEST)
        return add_cors_headers(response)

    # Try to find user by username or email
    try:
        user = None
        user_obj = None
        
        # First try exact username match
        try:
            user_obj = User.objects.get(username=username)
            logger.info(f"Found user by username: {username}")
            user = authenticate(request, username=user_obj.username, password=password)
            if user:
                logger.info(f"Successfully authenticated user by username: {username}")
        except User.DoesNotExist:
            logger.info(f"No user found with username: {username}, trying email...")
            
        # If username auth fails, try email
        if not user:
            try:
                user_obj = User.objects.get(email=username)
                logger.info(f"Found user by email: {username} -> {user_obj.username}")
                user = authenticate(request, username=user_obj.username, password=password)
                if user:
                    logger.info(f"Successfully authenticated user by email: {username}")
            except User.DoesNotExist:
                logger.warning(f"No user found with email: {username}")
            except Exception as e:
                logger.error(f"Error during email lookup: {str(e)}")
                
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        user = None

    if user is not None and user.is_active:
        try:
            login(request, user)
            refresh = RefreshToken.for_user(user)
            
            # Get company information safely
            company_data = {
                'company_id': None,
                'company_name': None,
                'user_company_id': None,
                'user_company_name': None
            }
            
            # Try to get company info if available
            if hasattr(user, 'company') and user.company:
                company_data.update({
                    'company_id': user.company.id,
                    'company_name': user.company.name
                })
            
            if hasattr(user, 'user_company') and user.user_company:
                company_data.update({
                    'user_company_id': user.user_company.id,
                    'user_company_name': user.user_company.name
                })

            access_token = str(refresh.access_token)
            # Send clean token without any prefix
            response_data = {
                'status': 'success',
                'message': 'Login successful',
                'data': {
                    'token': access_token,  # JWT token without prefix
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        **company_data
                    }
                }
            }
            
            logger.info(f"Login successful for user: {user.username}")
            response = Response(response_data, status=status.HTTP_200_OK)
            return add_cors_headers(response)
            
        except Exception as e:
            logger.error(f"Error during login process: {str(e)}")
            response = Response({
                'status': 'error',
                'message': 'Internal server error during login',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return add_cors_headers(response)
    else:
        error_msg = 'Invalid credentials'
        if user is not None and not user.is_active:
            error_msg = 'Account is disabled'
            
        logger.warning(f"Login failed: {error_msg}")
        response = Response({
            'status': 'error',
            'message': error_msg
        }, status=status.HTTP_401_UNAUTHORIZED)
        return add_cors_headers(response)

@csrf_exempt
@api_view(['POST', 'OPTIONS'])
def logout_view(request):
    """Handle logout requests"""
    if request.method == 'OPTIONS':
        return add_cors_headers(Response(status=status.HTTP_200_OK))
        
    if request.user.is_authenticated:
        try:
            logout(request)
            logger.info(f"User logged out successfully: {request.user.username}")
            response = Response({
                'status': 'success',
                'message': 'Logged out successfully'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            response = Response({
                'status': 'error',
                'message': 'Error during logout',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        logger.warning("Logout attempted without authentication")
        response = Response({
            'status': 'error',
            'message': 'Not authenticated'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    return add_cors_headers(response)

@csrf_exempt
@api_view(['POST', 'OPTIONS'])
def get_user_api_token(request):
    """Generate or retrieve API token for authenticated user"""
    
    if request.method == 'OPTIONS':
        return add_cors_headers(Response(status=status.HTTP_200_OK))
    
    if not request.user.is_authenticated:
        response = Response({
            'status': 'error',
            'message': 'User not authenticated'
        }, status=status.HTTP_401_UNAUTHORIZED)
        return add_cors_headers(response)
    
    try:
        # Try to get existing token
        token = Token.objects.get(user=request.user)
        logger.debug(f"Retrieved existing API token for user: {request.user.username}")
    except Token.DoesNotExist:
        # Create new token if none exists
        token = Token.objects.create(user=request.user)
        logger.info(f"Created new API token for user: {request.user.username}")
    except Exception as e:
        logger.error(f"Error managing API token: {str(e)}")
        response = Response({
            'status': 'error',
            'message': 'Error generating API token',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return add_cors_headers(response)
    
    # Return standardized response format
    response = Response({
        'status': 'success',
        'data': {
            'api_token': token.key,
            'token': token.key  # For backward compatibility
        },
        'message': 'API token retrieved successfully'
    }, status=status.HTTP_200_OK)
    
    return add_cors_headers(response)
