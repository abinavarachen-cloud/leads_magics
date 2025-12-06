import uuid
import time
from django.db import models
from django.core.validators import EmailValidator
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, AbstractUser
from ckeditor.fields import RichTextField
from ckeditor_uploader.fields import RichTextUploadingField
from api.manager import CustomUserManager  # we will create this
from django_ckeditor_5.fields import CKEditor5Field 
import pytz


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = None  # remove username completely

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Your additional fields
    is_admin = models.BooleanField(default=False)
    is_partner = models.BooleanField(default=False)
    otp = models.CharField(max_length=6, null=True, blank=True)
    company_id = models.IntegerField(null=True, blank=True)  # Replace with FK later
    is_module_user = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # No username

    objects = CustomUserManager()

    def __str__(self):
        return self.email



class Company(models.Model):
    company_name = models.CharField(max_length=100)
    domain = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=150, null=True, blank=True)
    industry = models.CharField(max_length=100, null=True, blank=True)
    company_email = models.EmailField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.company_name


class Client(models.Model):
    NURTURING_STAGES = [
        ("hot", "Hot - Highly Interested"),
        ("warm", "Warm - Moderately Interested"),
        ("cold", "Cold - Not Interested"),
    ]
    STATUS_CHOICES = [
        ("new", "New"),
        ("lost", "Lost"),
        ("won", "Won"),
    ]

    # Foreign Key to Company
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="clients", null=True, blank=True
    )

    # Contact Information
    client = models.CharField(max_length=100, null=True, blank=True)
    job_role = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    social_media = models.JSONField(null=True, blank=True, default=dict)
    status = models.CharField(
        max_length=50, choices=STATUS_CHOICES, null=True, blank=True, default="new"
    )
    remarks = models.TextField(null=True, blank=True)
    lead_owner = models.CharField(max_length=100, null=True, blank=True)
    nurturing_stage = models.CharField(
        max_length=10, choices=NURTURING_STAGES, default="warm", null=True, blank=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.client or f"Client {self.id}"


class Folder(models.Model):
    name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Folder"
        verbose_name_plural = "Folders"

    def __str__(self):
        return self.name


    
class List(models.Model):
    name = models.CharField(max_length=100)
    folder = models.ForeignKey(
        Folder,
        related_name="lists",
        on_delete=models.SET_NULL,  # or CASCADE if you want lists deleted with folder
        null=True,
        blank=True,
    )
    clients = models.ManyToManyField(Client, related_name="lists", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def count(self):
        """Dynamic count of clients in the list"""
        return self.clients.count()

class Template(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]
    
    # Basic information
    name = models.CharField(max_length=255, unique=True, help_text="Template name for identification")
    
    # Email content - using CKEditor5Field for rich text editing
    html_content = CKEditor5Field(
        config_name='extends',
        blank=True,
        null=True,
        help_text="HTML content of the email"
    )
    
    # Plain text fallback (optional)
    plain_text_content = models.TextField(
        blank=True, 
        null=True,
        help_text="Plain text version for email clients that don't support HTML"
    )
    
    # Template status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    total_sent = models.PositiveIntegerField(default=0, help_text="Total emails sent using this template")
    last_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Template variables documentation
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON list of available template variables e.g., ['{{name}}', '{{email}}', '{{link}}']"
    )
    
    # Thumbnail/preview
    thumbnail = models.ImageField(
        upload_to='email_templates/thumbnails/',
        null=True,
        blank=True,
        help_text="Template preview thumbnail"
    )
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
        indexes = [
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_html_content(self):
        """Get HTML content with fallback"""
        if self.html_content:
            return self.html_content
        # Convert plain text to basic HTML if no HTML content
        return f"<html><body><pre>{self.plain_text_content or ''}</pre></body></html>"
    
    def get_plain_text_content(self):
        """Get plain text content with fallback"""
        if self.plain_text_content:
            return self.plain_text_content
        
        # If no plain text, strip HTML tags from html_content
        import re
        if self.html_content:
            # Simple HTML tag removal
            text = re.sub(r'<[^>]*>', ' ', str(self.html_content))
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        
        return ""
    
    def save(self, *args, **kwargs):
        # Auto-generate plain text if not provided and HTML exists
        if self.html_content and not self.plain_text_content:
            import re
            text = re.sub(r'<[^>]*>', ' ', str(self.html_content))
            text = re.sub(r'\s+', ' ', text).strip()
            self.plain_text_content = text[:1000]  # Limit length
        
        super().save(*args, **kwargs)
    
    def render_template(self, context=None):
        """Render template with dynamic variables"""
        from django.template import Template, Context
        
        if context is None:
            context = {}
        
        # Render HTML content
        html_content = self.get_html_content()
        html_template = Template(html_content)
        rendered_html = html_template.render(Context(context))
        
        # Render plain text
        text_content = self.get_plain_text_content()
        if text_content:
            text_template = Template(text_content)
            rendered_text = text_template.render(Context(context))
        else:
            rendered_text = ""
        
        return {
            'html_content': rendered_html,
            'plain_text_content': rendered_text
        }
    
    def increment_usage(self):
        """Increment usage counter and update last used timestamp"""
        self.total_sent += 1
        self.last_used = timezone.now()
        self.last_sent_at = timezone.now()
        self.save(update_fields=['total_sent', 'last_used', 'last_sent_at', 'updated_at'])
    
    
    
class EmailCampaign(models.Model):
    # Campaign types
    CAMPAIGN_TYPE_CHOICES = [
        ("newsletter", "Newsletter"),
        ("transactional", "Transactional"),
        ("promotional", "Promotional"),
        ("automated", "Automated"),
    ]

    # Unified, expressive lifecycle statuses
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("save_as_draft", "Save as Draft"),
        ("send_test_email", "Send Test Email"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("paused", "Paused"),
        ("sent", "Sent"),
        ("cancelled", "Cancelled"),
    ]

    # Core fields
    campaign_name = models.CharField(max_length=255)
    campaign_type = models.CharField(
        max_length=50, choices=CAMPAIGN_TYPE_CHOICES, default="promotional"
    )

    # Content & subject - Make subject_line required
    subject_line = models.CharField(max_length=255, default="No Subject")
    preview_text = models.CharField(max_length=500, blank=True)
    template = models.ForeignKey(
        "EmailTemplate", on_delete=models.SET_NULL, null=True, blank=True
    )
    custom_content = models.TextField(
        null=True, blank=True, help_text="Optional override HTML/text content"
    )
    template = models.ForeignKey('Template', on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    custom_content = models.TextField(null=True, blank=True, help_text="Optional override HTML/text content")

    # Sender
    sender_name = models.CharField(max_length=255, null=True, blank=True)
    sender_email = models.EmailField(
        validators=[EmailValidator()], null=True, blank=True
    )

    # Audience lists
    contact_lists = models.ManyToManyField("List", related_name="campaigns", blank=True)
    do_not_send_lists = models.ManyToManyField(
        "List", related_name="excluded_campaigns", blank=True)
    # Recipient configuration
    sent_lists = models.ManyToManyField('List', related_name='sent_list', blank=True)
    do_notsent_lists = models.ManyToManyField('List', related_name='do_notsent_lists', blank=True)
    
    # Email headers
    reply_to = models.EmailField(null=True, blank=True)
    custom_headers = models.JSONField(default=dict, blank=True)
    
    # Tracking configuration
    enable_tracking = models.BooleanField(default=True)
    track_opens = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)
    
    # Email format
    email_format = models.CharField(
        max_length=10,
        choices=[('html', 'HTML'), ('text', 'Plain Text'), ('both', 'Both')],
        default='both'
    )

    # Extra metadata
    opportunities = models.JSONField(default=dict, blank=True)
    test_email_recipients = models.TextField(
        blank=True, help_text="Comma-separated test emails"
    )

    # Status & timestamps
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # Optional helper flags
    selected = models.BooleanField(default=False)

    # Template variables for this campaign
    template_variables = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object with template variable values"
    )

    class Meta:
        db_table = "campaigns"
        ordering = ["-created_at"]
        verbose_name = "Email Campaign"
        verbose_name_plural = "Email Campaigns"

    def __str__(self):
        return self.campaign_name or f"Campaign {self.pk}"

    def get_email_content(self):

        if self.custom_content:
            return self.custom_content
        
        # Use template content if available
        if self.template:
            # Get the template instance
            template_obj = self.template
            
            # Check if template has html_content
            if hasattr(template_obj, 'html_content') and template_obj.html_content:
                html_content = template_obj.html_content
                
                # If we have template variables, try to render them
                if self.template_variables:
                    try:
                        from django.template import Template, Context
                        # Create Template object from the HTML string
                        template = Template(html_content)
                        # Create Context with template variables
                        context = Context(self.template_variables)
                        # Render the template
                        rendered_html = template.render(context)
                        return rendered_html
                    except Exception as e:
                        # Log error but return unrendered content as fallback
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error rendering template for campaign {self.id}: {str(e)}")
                        return html_content
                else:
                    # No template variables, return raw HTML
                    return html_content
            else:
                print(f"DEBUG: Template {template_obj.id} has no html_content")
                return ""
        
        # No content found
        print(f"DEBUG: Campaign {self.id} has no template and no custom_content")
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
        if self.template and getattr(self.template, "content", None):
            return self.template.content
        return ""

    def get_email_subject(self):
        if self.subject_line:
            return self.subject_line
        if self.template and getattr(self.template, "subject", None):
            return self.template.subject
        return "No Subject"
    
    def get_plain_text_content(self):
        """Get plain text version"""
        if self.template:
            rendered = self.template.render_template(self.template_variables)
            return rendered['plain_text_content']
        
        # Generate from HTML content
        import re
        html_content = self.get_email_content()
        text = re.sub(r'<[^>]*>', ' ', str(html_content))
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def get_email_subject(self):
        """Get email subject with template variables"""
        from django.template import Template, Context
        
        if not self.subject_line:
            return "No Subject"
        
        # Render subject with template variables
        template = Template(self.subject_line)
        context = Context(self.template_variables or {})
        return template.render(context)
    
    
    def get_preview_text(self):
        """Get preview text for email clients"""
        return self.preview_text or ''

    # --- Metrics (computed from related recipients) ---
    @property
    def recipients_queryset(self):
        return self.recipients.all()

    @property
    def total_recipients(self):
        return self.recipients_queryset.count()

    @property
    def total_sent(self):
        return self.recipients_queryset.filter(status="sent").count()

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
        return self.recipients_queryset.filter(status="failed").count()

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
        return (
            (self.total_recipients - self.total_failed) / self.total_recipients
        ) * 100

    def get_recipients_stats(self):
        return {
            "total_recipients": self.total_recipients,
            "total_sent": self.total_sent,
            "total_opens": self.total_opens,
            "total_clicks": self.total_clicks,
            "total_unsubscribes": self.total_unsubscribes,
            "total_failed": self.total_failed,
            "open_rate": round(self.open_rate, 2),
            "click_rate": round(self.click_rate, 2),
            "delivery_rate": round(self.delivery_rate, 2),
        }
    
    def send_test_email(self, test_emails=None):
        """Send test email for this campaign"""
        from django.core.mail import EmailMultiAlternatives
        
        if test_emails is None:
            if self.test_email_recipients:
                test_emails = [email.strip() for email in self.test_email_recipients.split(',')]
            else:
                return False, "No test email recipients specified"
        
        try:
            html_content = self.get_email_content()
            plain_text = self.get_plain_text_content()
            subject = self.get_email_subject()
            
            email = EmailMultiAlternatives(
                subject=f"[TEST] {subject}",
                body=plain_text,
                from_email=self.sender_email or settings.DEFAULT_FROM_EMAIL,
                to=test_emails
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            return True, f"Test email sent to {', '.join(test_emails)}"
            
        except Exception as e:
            return False, str(e)    



class EmailRecipient(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("opened", "Opened"),
        ("clicked", "Clicked"),
        ("unsubscribed", "Unsubscribed"),
    ]

    campaign = models.ForeignKey(
        EmailCampaign, on_delete=models.CASCADE, related_name="recipients"
    )
    contact = models.ForeignKey(
        "Client", on_delete=models.CASCADE, related_name="email_recipients"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
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
        unique_together = ("campaign", "contact")
        ordering = ["-created_at"]

    def __str__(self):
        name = (
            getattr(self.contact, "name", None)
            or getattr(self.contact, "email", None)
            or str(self.tracking_id)
        )
        return f"{name} — {self.campaign.campaign_name} ({self.status})"

    def tracking_pixel_url(self):
        """
        Build absolute tracking pixel URL with cache-buster to avoid proxy caching.
        """
        path = reverse("track_email_open", args=[str(self.tracking_id)])
        domain = getattr(settings, "DOMAIN", "").rstrip("/")
        if not domain:
            return f"{path}?t={int(time.time())}"
        return f"{domain}{path}?t={int(time.time())}"

    # helper updates
    def mark_sent(self, when=None):
        self.status = "sent"
        self.sent_at = when if when else models.functions.Now()
        self.save(update_fields=["status", "sent_at"])

    def mark_opened(self, when=None):
        if not self.opened_at:
            self.opened_at = when if when else models.functions.Now()
        self.status = "opened"
        self.save(update_fields=["status", "opened_at"])

    def mark_clicked(self, when=None):
        if not self.clicked_at:
            self.clicked_at = when if when else models.functions.Now()
        self.status = "clicked"
        self.save(update_fields=["status", "clicked_at"])

    def mark_unsubscribed(self, when=None):
        self.unsubscribed_at = when if when else models.functions.Now()
        self.status = "unsubscribed"
        self.save(update_fields=["status", "unsubscribed_at"])
        self.status = 'unsubscribed'
        self.save(update_fields=['status', 'unsubscribed_at'])
        
        
        
        
