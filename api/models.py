import uuid
import time
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import EmailValidator
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from ckeditor_uploader.fields import RichTextUploadingField


class Company(models.Model):
    # Company Information
    company_name = models.CharField(max_length=100)
    domain = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=150, null=True, blank=True)
    industry = models.CharField(max_length=100, null=True, blank=True)
    company_email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Companies"
    
    def __str__(self):
        return self.company_name


class Client(models.Model):
    NURTURING_STAGES = [
        ('hot', 'Hot - Highly Interested'),
        ('warm', 'Warm - Moderately Interested'),
        ('cold', 'Cold - Not Interested'),
    ]
    
    # Foreign Key to Company
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='clients',
        null=True, 
        blank=True
    )
    
    # Contact Information
    client = models.CharField(max_length=100, null=True, blank=True)
    job_role = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    social_media = models.JSONField(null=True, blank=True, default=dict)
    status = models.CharField(max_length=50, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    lead_owner = models.CharField(max_length=100, null=True, blank=True)
    nurturing_stage = models.CharField(
        max_length=10, 
        choices=NURTURING_STAGES, 
        default='warm',
        null=True, 
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.client or f"Client {self.id}"


class List(models.Model):
    name = models.CharField(max_length=100)
    folder = models.CharField(max_length=100, null=True, blank=True)
    clients = models.ManyToManyField(Client, related_name='lists', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def count(self):
        """Dynamic count of clients in the list"""
        return self.clients.count()


class EmailTemplateCategory(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class EmailTemplate(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(EmailTemplateCategory, on_delete=models.CASCADE,null=True,blank=True)
    subject = models.CharField(max_length=255,null=True,blank=True)
    content = RichTextUploadingField(null=True, blank=True,config_name='default')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    total_recipients = models.PositiveIntegerField(default=0)
    selected = models.BooleanField(default=False,null=True,blank=True)

    def get_email_content(self):
        if self.content:
            return self.content
        return ""

    def get_email_subject(self):
        return self.subject or "No Subject"
    
    def __str__(self):
        return self.name
    
    
class EmailCampaign(models.Model):
    # Campaign types
    CAMPAIGN_TYPE_CHOICES = [
        ('newsletter', 'Newsletter'),
        ('transactional', 'Transactional'),
        ('promotional', 'Promotional'),
        ('automated', 'Automated'),
    ]

    # Unified, expressive lifecycle statuses
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('save_as_draft', 'Save as Draft'),
        ('send_test_email', 'Send Test Email'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('paused', 'Paused'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
    ]

    # Core fields
    campaign_name = models.CharField(max_length=255)
    campaign_type = models.CharField(max_length=50, choices=CAMPAIGN_TYPE_CHOICES, default='promotional')

    # Content & subject
    subject_line = models.CharField(max_length=255, blank=True, default="No Subject")
    preview_text = models.CharField(max_length=500, blank=True)
    template = models.ForeignKey('EmailTemplate', on_delete=models.SET_NULL, null=True, blank=True)
    custom_content = models.TextField(null=True, blank=True, help_text="Optional override HTML/text content")

    # Sender
    sender_name = models.CharField(max_length=255, null=True, blank=True)
    sender_email = models.EmailField(validators=[EmailValidator()], null=True, blank=True)

    # Audience lists
    contact_lists = models.ManyToManyField('List', related_name='campaigns', blank=True)
    do_not_send_lists = models.ManyToManyField('List', related_name='excluded_campaigns', blank=True)

    # Extra metadata
    opportunities = models.JSONField(default=dict, blank=True)
    test_email_recipients = models.TextField(blank=True, help_text="Comma-separated test emails")

    # Status & timestamps
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # Optional helper flags
    selected = models.BooleanField(default=False)

    class Meta:
        db_table = 'campaigns'
        ordering = ['-created_at']
        verbose_name = "Email Campaign"
        verbose_name_plural = "Email Campaigns"

    def __str__(self):
        return self.campaign_name or f"Campaign {self.pk}"
    
    def get_email_content(self):
        
        if self.custom_content:
            return self.custom_content
        elif self.template and self.template.content:
            return self.template.content
        return ""
    
    def get_email_subject(self):
   
        if self.subject_line:
            return self.subject_line
        elif self.template and self.template.subject:
            return self.template.subject
        return "No Subject"

    # --- Content helpers (fallback logic) ---
    def get_email_content(self):
        if self.custom_content:
            return self.custom_content
        if self.template and getattr(self.template, 'content', None):
            return self.template.content
        return ""

    def get_email_subject(self):
        if self.subject_line:
            return self.subject_line
        if self.template and getattr(self.template, 'subject', None):
            return self.template.subject
        return "No Subject"

    # --- Metrics (computed from related recipients) ---
    @property
    def recipients_queryset(self):
        return self.recipients.all()

    @property
    def total_recipients(self):
        return self.recipients_queryset.count()

    @property
    def total_sent(self):
        return self.recipients_queryset.filter(status='sent').count()

    @property
    def total_opens(self):
        return self.recipients_queryset.filter(opened_at__isnull=False).count()

    @property
    def total_clicks(self):
        return self.recipients_queryset.filter(clicked_at__isnull=False).count()

    @property
    def total_unsubscribes(self):
        return self.recipients_queryset.filter(unsubscribed_at__isnull=False).count()

    @property
    def total_failed(self):
        return self.recipients_queryset.filter(status='failed').count()

    @property
    def open_rate(self):
        if self.total_sent == 0:
            return 0.0
        return (self.total_opens / self.total_sent) * 100

    @property
    def click_rate(self):
        if self.total_opens == 0:
            return 0.0
        return (self.total_clicks / self.total_opens) * 100

    @property
    def delivery_rate(self):
        if self.total_recipients == 0:
            return 0.0
        return ((self.total_recipients - self.total_failed) / self.total_recipients) * 100

    def get_recipients_stats(self):
        return {
            'total_recipients': self.total_recipients,
            'total_sent': self.total_sent,
            'total_opens': self.total_opens,
            'total_clicks': self.total_clicks,
            'total_unsubscribes': self.total_unsubscribes,
            'total_failed': self.total_failed,
            'open_rate': round(self.open_rate, 2),
            'click_rate': round(self.click_rate, 2),
            'delivery_rate': round(self.delivery_rate, 2),
        }


class EmailRecipient(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('unsubscribed', 'Unsubscribed'),
    ]

    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='recipients')
    contact = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='email_recipients')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tracking_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # delivery / engagement timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    # optional failure metadata
    failed_reason = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('campaign', 'contact')
        ordering = ['-created_at']

    def __str__(self):
        name = getattr(self.contact, 'name', None) or getattr(self.contact, 'email', None) or str(self.tracking_id)
        return f"{name} — {self.campaign.campaign_name} ({self.status})"

    def tracking_pixel_url(self):
        """
        Build absolute tracking pixel URL with cache-buster to avoid proxy caching.
        """
        path = reverse('track_email_open', args=[str(self.tracking_id)])
        domain = getattr(settings, 'DOMAIN', '').rstrip('/')
        if not domain:
            return f"{path}?t={int(time.time())}"
        return f"{domain}{path}?t={int(time.time())}"

    # helper updates
    def mark_sent(self, when=None):
        self.status = 'sent'
        self.sent_at = when if when else models.functions.Now()
        self.save(update_fields=['status', 'sent_at'])

    def mark_opened(self, when=None):
        if not self.opened_at:
            self.opened_at = when if when else models.functions.Now()
        self.status = 'opened'
        self.save(update_fields=['status', 'opened_at'])

    def mark_clicked(self, when=None):
        if not self.clicked_at:
            self.clicked_at = when if when else models.functions.Now()
        self.status = 'clicked'
        self.save(update_fields=['status', 'clicked_at'])

    def mark_unsubscribed(self, when=None):
        self.unsubscribed_at = when if when else models.functions.Now()
        self.status = 'unsubscribed'
        self.save(update_fields=['status', 'unsubscribed_at'])
        
        
        
from django.db import models
from django.contrib.postgres.fields import JSONField
from ckeditor_uploader.fields import RichTextUploadingField


# class EmailTemplateCategory(models.Model):
#     """Categories to organize templates (e.g., Newsletter, Promotional, Transactional)"""
#     name = models.CharField(max_length=255)
#     description = models.TextField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         verbose_name_plural = "Email Template Categories"
#         ordering = ['name']

#     def __str__(self):
#         return self.name


# class EmailTemplate(models.Model):
#     """Main email template model with block-based design"""
    
#     TEMPLATE_TYPE_CHOICES = [
#         ('custom', 'Custom Template'),
#         ('pre_built', 'Pre-Built Template'),
#         ('team', 'Team Template'),
#     ]
    
#     # Basic Info
#     name = models.CharField(max_length=255, help_text="Template name for identification")
#     category = models.ForeignKey(
#         EmailTemplateCategory, 
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='templates'
#     )
#     template_type = models.CharField(
#         max_length=20,
#         choices=TEMPLATE_TYPE_CHOICES,
#         default='custom'
#     )
#     description = models.TextField(null=True, blank=True)
    
#     # Email Content
#     subject = models.CharField(
#         max_length=255,
#         null=True,
#         blank=True,
#         help_text="Email subject line"
#     )
#     preview_text = models.CharField(
#         max_length=150,
#         null=True,
#         blank=True,
#         help_text="Preview text shown in email clients"
#     )
    
#     # Template Design Storage
#     # Stores the block-based design structure as JSON
#     design_json = models.JSONField(
#         default=dict,
#         blank=True,
#         help_text="Stores the block structure of the email template"
#     )
    
#     # Legacy HTML content (for backward compatibility or direct HTML editing)
#     html_content = models.TextField(
#         null=True,
#         blank=True,
#         help_text="Compiled HTML or direct HTML content"
#     )
    
#     # Global Styles
#     global_styles = models.JSONField(
#         default=dict,
#         blank=True,
#         help_text="Global styling options (colors, fonts, etc.)"
#     )
    
#     # Thumbnail for template preview
#     thumbnail = models.ImageField(
#         upload_to='email_templates/thumbnails/',
#         null=True,
#         blank=True,
#         help_text="Template preview image"
#     )
    
#     # Usage tracking
#     usage_count = models.PositiveIntegerField(
#         default=0,
#         help_text="Number of times this template has been used"
#     )
#     is_favorite = models.BooleanField(default=False)
    
#     # Timestamps
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     last_used_at = models.DateTimeField(null=True, blank=True)
    
#     class Meta:
#         ordering = ['-updated_at']
#         indexes = [
#             models.Index(fields=['template_type', 'category']),
#             models.Index(fields=['-created_at']),
#         ]

#     def __str__(self):
#         return self.name
    
#     def get_email_subject(self):
#         """Get the email subject with fallback"""
#         return self.subject or "No Subject"
    
#     def get_email_content(self):
#         """
#         Get email content, prioritizing compiled HTML over design JSON
#         """
#         if self.html_content:
#             return self.html_content
#         elif self.design_json:
#             return self.compile_blocks_to_html()
#         return ""
    
#     def compile_blocks_to_html(self):
#         """
#         Convert design_json blocks to HTML
#         This is a simplified version - you'll need to expand based on your needs
#         """
#         if not self.design_json or 'blocks' not in self.design_json:
#             return ""
        
#         html_parts = ['<div class="email-container">']
        
#         for block in self.design_json.get('blocks', []):
#             block_type = block.get('type')
            
#             if block_type == 'heading':
#                 html_parts.append(f'<h1 style="{block.get("styles", "")}">{block.get("content", "")}</h1>')
            
#             elif block_type == 'text':
#                 html_parts.append(f'<p style="{block.get("styles", "")}">{block.get("content", "")}</p>')
            
#             elif block_type == 'image':
#                 html_parts.append(f'<img src="{block.get("src", "")}" alt="{block.get("alt", "")}" style="{block.get("styles", "")}"/>')
            
#             elif block_type == 'button':
#                 html_parts.append(f'<a href="{block.get("href", "#")}" style="{block.get("styles", "")}">{block.get("text", "Click here")}</a>')
            
#             elif block_type == 'divider':
#                 html_parts.append(f'<hr style="{block.get("styles", "")}"/>')
            
#             elif block_type == 'spacer':
#                 height = block.get('height', '20px')
#                 html_parts.append(f'<div style="height: {height};"></div>')
            
#             elif block_type == 'social':
#                 social_links = block.get('links', [])
#                 html_parts.append('<div class="social-media">')
#                 for link in social_links:
#                     html_parts.append(f'<a href="{link.get("url", "#")}">{link.get("icon", "")}</a>')
#                 html_parts.append('</div>')
            
#             elif block_type == 'footer':
#                 html_parts.append(f'<footer style="{block.get("styles", "")}">{block.get("content", "")}</footer>')
            
#             elif block_type == 'columns':
#                 columns = block.get('columns', [])
#                 html_parts.append('<div class="columns" style="display: flex;">')
#                 for col in columns:
#                     html_parts.append(f'<div class="column" style="{col.get("styles", "")}">{col.get("content", "")}</div>')
#                 html_parts.append('</div>')
        
#         html_parts.append('</div>')
#         return ''.join(html_parts)
    
#     def increment_usage(self):
#         """Increment usage counter when template is used"""
#         self.usage_count += 1
#         self.last_used_at = models.functions.Now()
#         self.save(update_fields=['usage_count', 'last_used_at'])


# class EmailTemplateBlock(models.Model):
#     """
#     Individual blocks that make up a template
#     (Alternative approach if you want to store blocks as separate objects)
#     """
    
#     BLOCK_TYPES = [
#         ('hero', 'Hero Section'),
#         ('heading', 'Heading'),
#         ('text', 'Text Paragraph'),
#         ('image', 'Image'),
#         ('button', 'Button/CTA'),
#         ('divider', 'Divider Line'),
#         ('spacer', 'Spacer'),
#         ('columns', 'Columns Layout'),
#         ('social', 'Social Media Links'),
#         ('footer', 'Footer'),
#     ]
    
#     template = models.ForeignKey(
#         EmailTemplate,
#         on_delete=models.CASCADE,
#         related_name='blocks'
#     )
    
#     block_type = models.CharField(max_length=50, choices=BLOCK_TYPES)
#     order = models.PositiveIntegerField(default=0, help_text="Display order in template")
    
#     # Block Content (flexible JSON to store any block-specific data)
#     content_data = models.JSONField(
#         default=dict,
#         help_text="Block-specific content and configuration"
#     )
    
#     # Styling
#     styles = models.JSONField(
#         default=dict,
#         blank=True,
#         help_text="Custom styles for this block"
#     )
    
#     # Visibility
#     is_active = models.BooleanField(default=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         ordering = ['template', 'order']
#         indexes = [
#             models.Index(fields=['template', 'order']),
#         ]
    
#     def __str__(self):
#         return f"{self.template.name} - {self.get_block_type_display()} (Order: {self.order})"


# class EmailTemplateVersion(models.Model):
#     """
#     Version control for templates - save history of changes
#     """
#     template = models.ForeignKey(
#         EmailTemplate,
#         on_delete=models.CASCADE,
#         related_name='versions'
#     )
    
#     version_number = models.PositiveIntegerField()
#     design_json = models.JSONField()
#     html_content = models.TextField(null=True, blank=True)
#     global_styles = models.JSONField(default=dict)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     created_by = models.CharField(max_length=255, null=True, blank=True)  # Can be ForeignKey to User
#     change_notes = models.TextField(null=True, blank=True)
    
#     class Meta:
#         ordering = ['-version_number']
#         unique_together = ['template', 'version_number']
    
#     def __str__(self):
#         return f"{self.template.name} - v{self.version_number}"

