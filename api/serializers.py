# serializers.py
from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims inside token if needed
        token['user_id'] = user.id
        token['company_id'] = user.company_id

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # # Add extra fields to login response
        # data['user_id'] = self.user.id
        # data['company_id'] = self.user.company_id
        # data['email'] = self.user.email
        return data



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
                'industry': instance.company.industry,
                'domain': instance.company.domain,
                'company_email': instance.company.company_email
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
from django.utils import timezone
import uuid


class EmailTemplateCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateCategory
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['created_at']


class EmailTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'category', 'category_name',
            'subject', 'content', 'created_at',
            'sent_at', 'total_recipients', 'selected'
        ]
        read_only_fields = ['created_at', 'sent_at', 'total_recipients']


class ContactListSerializer(serializers.ModelSerializer):
    class Meta:
        model = List
        fields = ['id', 'name', 'created_at']


class EmailRecipientSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source='contact.client', read_only=True)
    contact_email = serializers.CharField(source='contact.email', read_only=True)

    class Meta:
        model = EmailRecipient
        fields = [
            'id', 'contact',
            'contact_name', 'contact_email',
            'status', 'tracking_id',
            'sent_at', 'opened_at', 'clicked_at', 'unsubscribed_at',
        ]


class EmailCampaignSerializer(serializers.ModelSerializer):
    contact_lists = serializers.PrimaryKeyRelatedField(
        queryset=List.objects.all(),
        many=True,
        required=False
    )
    do_not_send_lists = serializers.PrimaryKeyRelatedField(
        queryset=List.objects.all(),
        many=True,
        required=False
    )
    
    stats = serializers.SerializerMethodField()
    template_name = serializers.CharField(source='template.name', read_only=True)
    
    class Meta:
        model = EmailCampaign
        fields = [
            'id', 'campaign_name', 'campaign_type',
            'subject_line', 'preview_text',
            'template', 'template_name', 'custom_content',
            'sender_name', 'sender_email',
            'contact_lists', 'do_not_send_lists',
            'opportunities',
            'test_email_recipients',
            'status',
            'created_at', 'updated_at',
            'scheduled_at', 'sent_at',
            'selected',
            'stats',
        ]
        read_only_fields = ('created_at', 'updated_at', 'sent_at', 'stats', 'template_name')
    
    def get_stats(self, obj):
        return obj.get_recipients_stats()
    
    def validate(self, data):
        """Validate campaign data"""
        # Check if trying to update a sent campaign
        if self.instance and self.instance.status == 'sent':
            raise serializers.ValidationError("Cannot update a campaign that has already been sent")
        
        # Validate sender_email format
        if 'sender_email' in data and data['sender_email']:
            from django.core.validators import validate_email
            try:
                validate_email(data['sender_email'])
            except:
                raise serializers.ValidationError("Invalid sender email format")
        
        return data
    
    def create(self, validated_data):
        # Extract ManyToMany fields from validated_data
        contact_lists_data = validated_data.pop('contact_lists', [])
        do_not_send_lists_data = validated_data.pop('do_not_send_lists', [])
        
        # Set default status if not provided
        validated_data.setdefault('status', 'draft')
        
        # If template is provided but custom_content is empty,
        # auto-fill custom_content from template
        template = validated_data.get('template')
        custom_content = validated_data.get('custom_content', '')
        
        if template and not custom_content and hasattr(template, 'content'):
            validated_data['custom_content'] = template.content
        
        # If template is provided but subject_line is empty/not set,
        # auto-fill subject_line from template
        if template and not validated_data.get('subject_line') and hasattr(template, 'subject'):
            validated_data['subject_line'] = template.subject
        
        # Create the campaign instance
        campaign = EmailCampaign.objects.create(**validated_data)
        
        # Add ManyToMany relationships
        if contact_lists_data:
            campaign.contact_lists.set(contact_lists_data)
        
        if do_not_send_lists_data:
            campaign.do_not_send_lists.set(do_not_send_lists_data)
        
        return campaign
    
    def update(self, instance, validated_data):
        # Extract ManyToMany fields
        contact_lists_data = validated_data.pop('contact_lists', None)
        do_not_send_lists_data = validated_data.pop('do_not_send_lists', None)
        
        # Handle template changes
        template = validated_data.get('template')
        if template and not validated_data.get('custom_content'):
            # If changing template and no custom_content provided, update from template
            if hasattr(template, 'content'):
                validated_data['custom_content'] = template.content
        
        # Update regular fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update ManyToMany fields if provided
        if contact_lists_data is not None:
            instance.contact_lists.set(contact_lists_data)
        
        if do_not_send_lists_data is not None:
            instance.do_not_send_lists.set(do_not_send_lists_data)
        
        return instance
    
    
# Campaign action serializers
class CampaignSendTestSerializer(serializers.Serializer):

    test_email = serializers.CharField(required=True)
    
    
    def validate_test_email(self, value):
        """Validate and parse email string"""
        # Split by comma, semicolon, or newline
        import re
        emails = re.split(r'[,;\n]+', value.strip())
        
        # Clean up each email
        clean_emails = []
        for email in emails:
            email = email.strip()
            if email:  # Skip empty strings
                # Basic email validation
                if '@' in email and '.' in email:
                    clean_emails.append(email)
                else:
                    raise serializers.ValidationError(f"Invalid email format: {email}")
        
        if not clean_emails:
            raise serializers.ValidationError("At least one valid email is required")
        
        return clean_emails


class CampaignScheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()


class CampaignSendNowSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()
    
    
    
    