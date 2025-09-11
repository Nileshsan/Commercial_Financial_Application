from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.authtoken.models import Token

@api_view(['POST'])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({
            'error': 'Please provide both username and password'
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Login successful',
            'user_id': user.id,
            'username': user.username,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh)
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        return Response({
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)
    return Response({
        'error': 'Not logged in'
    }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def get_user_api_token(request):
    if not request.user.is_authenticated:
        return Response({
            'error': 'User not authenticated'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        token = Token.objects.get(user=request.user)
    except ObjectDoesNotExist:
        token = Token.objects.create(user=request.user)
    
    return Response({
        'token': token.key
    }, status=status.HTTP_200_OK)
