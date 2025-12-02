import uuid
import time
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import EmailValidator
from django.utils import timezone
from django.conf import settings
from django.urls import reverse

class Template(models.Model):
    pass

class ContactList(models.Model):
    pass




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
        ('save_as_draft', 'Save as Draft'),  # optional alias
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
    template = models.ForeignKey('Template', on_delete=models.SET_NULL, null=True, blank=True)
    custom_content = models.TextField(null=True, blank=True, help_text="Optional override HTML/text content")

    # Sender
    sender_name = models.CharField(max_length=255, null=True, blank=True)
    sender_email = models.EmailField(validators=[EmailValidator()], null=True, blank=True)

    # Audience lists
    contact_lists = models.ManyToManyField('ContactList', related_name='campaigns', blank=True)
    do_not_send_lists = models.ManyToManyField('ContactList', related_name='excluded_campaigns', blank=True)

    # Extra metadata
    opportunities = models.JSONField(default=dict, blank=True)  # optional business data
    test_email_recipients = models.TextField(blank=True, help_text="Comma-separated test emails")

    # Status & timestamps
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
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

    # --- Sending helpers (stubs) ---
    def send_test_emails(self):
        if not self.test_email_recipients:
            return False
        emails = [e.strip() for e in self.test_email_recipients.split(',') if e.strip()]
        # TODO: implement real send logic (use Celery/RQ, template rendering, Recipient creation)
        return emails

    def send_campaign(self):
        # minimal validations
        if not self.contact_lists.exists():
            return False

        self.status = 'sending'
        self.save(update_fields=['status', 'updated_at'])
        # TODO: queue send tasks; create recipients; update sent_at when done
        return True

    # --- Metrics (computed from related recipients) ---
    @property
    def recipients_queryset(self):
        return self.recipients.all()  # related_name set on EmailRecipient below

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
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, related_name='email_recipients')
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
        # reverse should point to view name that handles open tracking: 'track_email_open'
        path = reverse('track_email_open', args=[str(self.tracking_id)])
        domain = getattr(settings, 'DOMAIN', '').rstrip('/')
        if not domain:
            # fallback: build relative path
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

    
    
