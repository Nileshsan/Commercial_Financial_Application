from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

class APIException(Exception):
    def __init__(self, message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is None:
        if isinstance(exc, APIException):
            response = Response({
                'error': exc.message,
                'status': 'error'
            }, status=exc.status_code)
        else:
            logger.error(f"Unhandled exception: {str(exc)}")
            response = Response({
                'error': 'An unexpected error occurred',
                'detail': str(exc),
                'status': 'error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response
