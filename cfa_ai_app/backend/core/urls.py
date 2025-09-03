from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .views import admin_frontend, create_company, create_user

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    A simple health check endpoint that doesn't require authentication
    """
    return Response({
        'status': 'healthy',
        'message': 'API is running'
    })

urlpatterns = [
    path('api/health/', health_check, name='health-check'),
    path('admin-frontend/', admin_frontend, name='admin-frontend'),
    path('api/create-company/', create_company, name='create-company'),
    path('api/create-user/', create_user, name='create-user'),
    path('api/health-check/', health_check, name='health-check'),
]
