# serializers.py
from rest_framework import serializers
from .models import *

class CompanySerializer(serializers.ModelSerializer):
    client_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'client_count']
    
    def get_client_count(self, obj):
        return obj.clients.count()

class ClientSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        source='company',
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.company:
            representation['company'] = {
                'id': instance.company.id,
                'company_name': instance.company.company_name,
                'location': instance.company.location,
                'industry': instance.company.industry
            }
        else:
            representation['company'] = None
        return representation

class ListSerializer(serializers.ModelSerializer):
    count = serializers.IntegerField(read_only=True)
    client_ids = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        many=True,
        write_only=True,
        required=False,
        source='clients'
    )
    
    class Meta:
        model = List
        fields = ['id', 'name', 'folder', 'count', 'client_ids', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'count']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['clients'] = ClientSerializer(instance.clients.all(), many=True).data
        return representation

class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = '__all__'
