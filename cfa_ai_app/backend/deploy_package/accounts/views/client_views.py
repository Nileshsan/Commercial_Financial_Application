from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from accounts.models import (
    Client, UserCompany, ClientCategory,
    ClientDocument, ClientActivity
)
from accounts.serializers import (
    ClientRegistrationSerializer, ClientCategorySerializer,
    ClientDocumentSerializer, ClientActivitySerializer
)
from accounts.authentication import BearerTokenAuthentication

class ClientRegistrationViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientRegistrationSerializer
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'email', 'phone', 'tax_number', 'tags']
    ordering_fields = ['name', 'created_at', 'last_activity_date', 'risk_level']
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """
        Filter clients based on user's company and query parameters
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user.is_superuser:
            queryset = queryset.filter(company=user.company)

        # Filter by client type
        client_type = self.request.query_params.get('client_type', None)
        if client_type:
            queryset = queryset.filter(client_type=client_type)

        # Filter by risk level
        risk_level = self.request.query_params.get('risk_level', None)
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)

        # Filter by category
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category__name=category)

        # Filter by verification status
        is_verified = self.request.query_params.get('is_verified', None)
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')

        # Filter by tags
        tags = self.request.query_params.getlist('tags', None)
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])

        # Filter by revenue range
        min_revenue = self.request.query_params.get('min_revenue', None)
        max_revenue = self.request.query_params.get('max_revenue', None)
        if min_revenue:
            queryset = queryset.filter(annual_revenue__gte=float(min_revenue))
        if max_revenue:
            queryset = queryset.filter(annual_revenue__lte=float(max_revenue))

        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Register a new client with documents
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        try:
            client = serializer.save()
            return Response({
                'status': 'success',
                'message': 'Client registered successfully',
                'data': self.get_serializer(client).data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate a client
        """
        client = self.get_object()
        client.is_active = False
        client.save()
        client.log_activity(
            'STATUS_CHANGE',
            'Client deactivated',
            request.user
        )
        return Response({
            'status': 'success',
            'message': 'Client deactivated successfully'
        })

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate a client
        """
        client = self.get_object()
        client.is_active = True
        client.save()
        client.log_activity(
            'STATUS_CHANGE',
            'Client activated',
            request.user
        )
        return Response({
            'status': 'success',
            'message': 'Client activated successfully'
        })

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verify a client
        """
        client = self.get_object()
        client.is_verified = True
        client.save()
        client.log_activity(
            'STATUS_CHANGE',
            'Client verified',
            request.user
        )
        return Response({
            'status': 'success',
            'message': 'Client verified successfully'
        })

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        """
        Upload a document for a client
        """
        client = self.get_object()
        serializer = ClientDocumentSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(client=client)
            client.log_activity(
                'DOCUMENT_ADDED',
                f'Document uploaded: {serializer.data["document_type"]}',
                request.user
            )
            return Response({
                'status': 'success',
                'message': 'Document uploaded successfully',
                'data': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """
        Get client activities
        """
        client = self.get_object()
        activities = client.activities.all().order_by('-performed_at')
        serializer = ClientActivitySerializer(activities, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get client statistics
        """
        queryset = self.get_queryset()
        return Response({
            'total_clients': queryset.count(),
            'active_clients': queryset.filter(is_active=True).count(),
            'verified_clients': queryset.filter(is_verified=True).count(),
            'client_types': {
                client_type: queryset.filter(client_type=client_type).count()
                for client_type, _ in Client.CLIENT_TYPES
            },
            'risk_levels': {
                risk_level: queryset.filter(risk_level=risk_level).count()
                for risk_level, _ in Client.RISK_LEVELS
            }
        })
