from rest_framework import serializers
from django.utils import timezone
from accounts.models import (
    UserCompany, Company, Client, ClientCategory,
    ClientDocument, ClientActivity
)

class ClientDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientDocument
        fields = ['id', 'document_type', 'file', 'uploaded_at', 'notes', 'is_verified']
        read_only_fields = ['id', 'uploaded_at', 'is_verified']

class ClientActivitySerializer(serializers.ModelSerializer):
    performed_by = serializers.StringRelatedField()
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)

    class Meta:
        model = ClientActivity
        fields = ['id', 'activity_type', 'activity_type_display', 'description', 
                 'performed_by', 'performed_at']
        read_only_fields = ['id', 'performed_at']

class ClientCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientCategory
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']

class ClientRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(max_length=15, required=True)
    company_name = serializers.CharField(max_length=255, required=True)
    category_name = serializers.CharField(max_length=100, required=False)
    documents = ClientDocumentSerializer(many=True, required=False)
    activities = ClientActivitySerializer(many=True, read_only=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    
    class Meta:
        model = Client
        fields = [
            'id', 'name', 'email', 'phone', 'address', 
            'company_name', 'category_name', 'client_type',
            'tax_number', 'website', 'annual_revenue',
            'employee_count', 'risk_level', 'credit_limit',
            'tags', 'is_active', 'is_verified', 'created_at',
            'updated_at', 'last_activity_date', 'documents',
            'activities'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 
                           'last_activity_date', 'is_verified']

    def create(self, validated_data):
        company_name = validated_data.pop('company_name')
        category_name = validated_data.pop('category_name', None)
        documents_data = validated_data.pop('documents', [])
        
        # Create or get the company
        company, _ = UserCompany.objects.get_or_create(
            name=company_name
        )
        
        # Create or get the category if provided
        category = None
        if category_name:
            category, _ = ClientCategory.objects.get_or_create(
                name=category_name,
                company=company
            )
        
        # Create the client
        client = Client.objects.create(
            **validated_data,
            company=company,
            category=category,
            last_activity_date=timezone.now()
        )
        
        # Create documents
        for doc_data in documents_data:
            ClientDocument.objects.create(client=client, **doc_data)
        
        # Log the creation activity
        client.log_activity(
            'CREATED',
            'Client profile created',
            self.context['request'].user if 'request' in self.context else None
        )
        
        return client

    def update(self, instance, validated_data):
        category_name = validated_data.pop('category_name', None)
        documents_data = validated_data.pop('documents', [])
        
        if category_name:
            category, _ = ClientCategory.objects.get_or_create(
                name=category_name,
                company=instance.company
            )
            instance.category = category
        
        # Update documents
        if documents_data:
            for doc_data in documents_data:
                ClientDocument.objects.create(client=instance, **doc_data)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Log the update activity
        instance.log_activity(
            'UPDATED',
            'Client information updated',
            self.context['request'].user if 'request' in self.context else None
        )
        
        return instance

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'address', 'api_key', 'created_at']
        read_only_fields = ['id', 'api_key', 'created_at']

class UserCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCompany
        fields = ['id', 'name', 'address', 'created_at']
        read_only_fields = ['id', 'created_at']
