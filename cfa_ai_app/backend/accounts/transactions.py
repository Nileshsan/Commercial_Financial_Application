from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def normalize_transactions(request):
    """
    Normalize and match transactions for the authenticated user's company.
    This endpoint processes and matches transactions after they've been synced.
    """
    try:
        user = request.user
        company = user.company
        
        # Add your transaction normalization logic here
        # For example:
        # normalize_company_transactions(company)
        
        return Response({
            'status': 'success',
            'message': 'Transactions normalized successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
