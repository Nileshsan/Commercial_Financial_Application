from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import get_user_model


class CustomTokenObtainPairView(APIView):
    """Accepts POST with either the configured USERNAME_FIELD (email) or
    'username' and returns JWT token pair using SimpleJWT's serializer.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        username_field = get_user_model().USERNAME_FIELD
        # Map 'username' to the actual USERNAME_FIELD if necessary
        if 'username' in data and username_field not in data:
            data[username_field] = data.get('username')

        serializer = TokenObtainPairSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            return Response(serializer.validated_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
