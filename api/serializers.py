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
from rest_framework import serializers
from .models import *
# from contacts.models import ContactList, Contact   # adjust import
from django.utils import timezone
import uuid


# ------------------------------
# Contact List Serializer
# ------------------------------
class ContactListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactList
        fields = ['id', 'name', 'created_at']


# ------------------------------
# Email Recipient Serializer
# ------------------------------
class EmailRecipientSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    contact_email = serializers.CharField(source='contact.email', read_only=True)

    class Meta:
        model = EmailRecipient
        fields = [
            'id', 'contact',
            'contact_name', 'contact_email',
            'status', 'tracking_id',
            'sent_at', 'opened_at', 'clicked_at', 'unsubscribed_at',
        ]


# ------------------------------
# Email Campaign Create/Update
# ------------------------------
class EmailCampaignSerializer(serializers.ModelSerializer):

    contact_lists = serializers.PrimaryKeyRelatedField(
        queryset=ContactList.objects.all(),
        many=True,
        required=False
    )
    do_not_send_lists = serializers.PrimaryKeyRelatedField(
        queryset=ContactList.objects.all(),
        many=True,
        required=False
    )

    # Show computed statistics
    stats = serializers.SerializerMethodField()

    class Meta:
        model = EmailCampaign
        fields = [
            'id', 'campaign_name', 'campaign_type',
            'subject_line', 'preview_text',
            'template', 'custom_content',
            'sender_name', 'sender_email',
            'contact_lists', 'do_not_send_lists',
            'opportunities',
            'test_email_recipients',
            'status',
            'created_by',
            'created_at', 'updated_at',
            'scheduled_at', 'sent_at',
            'selected',
            'stats',
        ]
        read_only_fields = ('created_by',)

    def get_stats(self, obj):
        return obj.get_recipients_stats()

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Allow updating status, lists, content, etc."""
        return super().update(instance, validated_data)




class CampaignSendTestSerializer(serializers.Serializer):
    test_email = serializers.EmailField()


class CampaignScheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()


class CampaignSendNowSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()
