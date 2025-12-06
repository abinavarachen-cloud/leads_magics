from rest_framework import serializers
from .models import *
from django.utils import timezone
import uuid
import pytz
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


class TemplateSerializer(serializers.ModelSerializer):
    html_content_preview = serializers.SerializerMethodField()
    plain_text_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Template
        fields = [
            'id',
            'name',
            'html_content',
            'html_content_preview',
            'plain_text_content',
            'plain_text_preview',
            'variables',
            'status',
            'total_sent',
            'last_used',
            'created_at',
            'updated_at',
            'thumbnail',
        ]
        read_only_fields = ['total_sent', 'last_used', 'created_at', 'updated_at']
    
    def get_html_content_preview(self, obj):
        """Get a preview of HTML content"""
        from django.utils.html import strip_tags
        if obj.html_content:
            text = strip_tags(str(obj.html_content))
            return text[:150] + '...' if len(text) > 150 else text
        return ""
    
    def get_plain_text_preview(self, obj):
        """Get a preview of plain text content"""
        if obj.plain_text_content:
            content = str(obj.plain_text_content)
            return content[:150] + '...' if len(content) > 150 else content
        return ""
    
    def validate_html_content(self, value):
        """Validate HTML content"""
        if value and len(str(value).strip()) == 0:
            raise serializers.ValidationError("HTML content cannot be empty")
        return value


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
    template_details = TemplateSerializer(source='template', read_only=True)
    stats = serializers.SerializerMethodField()
    sent_lists = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=List.objects.all(),
        required=False
    )
    do_notsent_lists = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=List.objects.all(),
        required=False
    )
    
    class Meta:
        model = EmailCampaign
        fields = [
            'id',
            'campaign_name',
            'campaign_type',
            'subject_line',
            'preview_text',
            'template',
            'template_details',
            'custom_content',
            'sender_name',
            'sender_email',
            'sent_lists',  # Updated to match your model
            'do_notsent_lists',  # Updated to match your model
            'reply_to',
            'custom_headers',
            'enable_tracking',
            'track_opens',
            'track_clicks',
            'email_format',
            'opportunities',
            'test_email_recipients',
            'status',
            'created_at',
            'updated_at',
            'scheduled_at',
            'sent_at',
            'selected',
            'template_variables',
            'stats',
        ]
        read_only_fields = ['created_at', 'updated_at', 'sent_at', 'stats']
    
    def get_stats(self, obj):
        return obj.get_recipients_stats()
    
    def validate_template_variables(self, value):
        """Validate template variables JSON"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Template variables must be a JSON object")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Ensure either template or custom_content is provided
        if not data.get('template') and not data.get('custom_content'):
            raise serializers.ValidationError({
                'template': 'Either template or custom content must be provided.',
                'custom_content': 'Either template or custom content must be provided.'
            })
        return data
    
    def create(self, validated_data):
        """Handle ManyToMany field creation"""
        sent_lists_data = validated_data.pop('sent_lists', [])
        do_notsent_lists_data = validated_data.pop('do_notsent_lists', [])
        
        campaign = EmailCampaign.objects.create(**validated_data)
        
        # Add sent lists
        if sent_lists_data:
            campaign.sent_lists.set(sent_lists_data)
        
        # Add do-not-send lists
        if do_notsent_lists_data:
            campaign.do_notsent_lists.set(do_notsent_lists_data)
        
        return campaign
    
    def update(self, instance, validated_data):
        """Handle ManyToMany field updates"""
        sent_lists_data = validated_data.pop('sent_lists', None)
        do_notsent_lists_data = validated_data.pop('do_notsent_lists', None)
        
        # Update instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update ManyToMany fields if provided
        if sent_lists_data is not None:
            instance.sent_lists.set(sent_lists_data)
        
        if do_notsent_lists_data is not None:
            instance.do_notsent_lists.set(do_notsent_lists_data)
        
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
    
    def validate_scheduled_at(self, value):
        """
        Ensure scheduled time is in the future
        Always return UTC time
        """
        # Make sure it's timezone-aware
        if not timezone.is_aware(value):
            # If no timezone, assume UTC
            value = pytz.UTC.localize(value)
        
        # Convert to UTC
        value_utc = value.astimezone(pytz.UTC)
        
        # Get current time in UTC
        current_time_utc = timezone.now().astimezone(pytz.UTC)
        
        # Validate it's in the future
        if value_utc <= current_time_utc:
            raise serializers.ValidationError(
                f"Scheduled time must be in the future. "
                f"Current UTC: {current_time_utc}, "
                f"Scheduled UTC: {value_utc}"
            )
        
        # Return UTC time
        return value_utc
    
    
class CampaignSendNowSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()