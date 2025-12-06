import os
import ssl
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import pytz


# ========== SSL SETUP ==========
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'

logger = logging.getLogger(__name__)

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import EmailCampaign, EmailRecipient, Client, Template
from django.utils.html import strip_tags
from django.template.loader import render_to_string
from datetime import datetime
from urllib.parse import quote
from django.core.mail import EmailMultiAlternatives


# ========== SMTP CONNECTION ==========
def create_smtp_connection():
    """Create SMTP connection with unverified SSL"""
    try:
        # Create unverified SSL context
        context = ssl._create_unverified_context()
        
        # Connect to Gmail SMTP
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=30)
        
        # Start TLS with unverified context
        server.starttls(context=context)
        
        # Login
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        
        logger.info("✅ SMTP connection established successfully")
        return server
        
    except Exception as e:
        logger.error(f"❌ Failed to create SMTP connection: {str(e)}")
        raise



def create_fallback_email_html(campaign, personalized_html, personalized_subject, 
                               contact, tracking_pixel_url, unsubscribe_url):
    """
    Create HTML email template as fallback when template file is missing
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{personalized_subject}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background-color: #f5f5f5;
            }}
            .email-container {{
                max-width: 600px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .email-header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px 20px;
                text-align: center;
            }}
            .campaign-name {{
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .preview-text {{
                font-size: 16px;
                opacity: 0.9;
                font-style: italic;
                margin-top: 10px;
            }}
            .email-body {{
                padding: 30px;
            }}
            .sender-info {{
                background: #f9f9f9;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
                border: 1px solid #eee;
            }}
            .email-footer {{
                background: #f9f9f9;
                padding: 20px;
                text-align: center;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
                color: #666;
            }}
            @media (max-width: 600px) {{
                .email-body {{
                    padding: 20px;
                }}
                .email-header {{
                    padding: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <div class="campaign-name">{campaign.campaign_name}</div>
                <div class="preview-text">{campaign.preview_text or ''}</div>
            </div>
            
            <div class="email-body">
                <div class="sender-info">
                    <p><strong>From:</strong> {campaign.sender_name or 'Our Company'} &lt;{campaign.sender_email or settings.DEFAULT_FROM_EMAIL}&gt;</p>
                    <p><strong>To:</strong> {contact.client or contact.email}</p>
                    <p><strong>Subject:</strong> {personalized_subject}</p>
                </div>
                
                <div class="email-content">
                    {personalized_html}
                </div>
            </div>
            
            <div class="email-footer">
                <p>
                    &copy; {datetime.now().year} {campaign.sender_name or 'Our Company'}. All rights reserved.<br>
                    <small>
                        <a href="{unsubscribe_url}" style="color: #666;">
                            Unsubscribe from this list
                        </a>
                    </small>
                </p>
            </div>
            
            <!-- Tracking Pixel -->
            <img src="{tracking_pixel_url}" alt="" width="1" height="1" style="display: none;">
        </div>
    </body>
    </html>
    """



# ========== EMAIL SENDING TASKS ==========
@shared_task
def send_campaign_emails(campaign_id):
    """
    Main task to send campaign emails using direct SMTP connection
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        # Update campaign status
        campaign.status = "sending"
        campaign.save(update_fields=['status', 'updated_at'])
        
        # Get pending recipients
        recipients = campaign.recipients.filter(status='pending')
        
        logger.info(f"✅ Starting to send campaign '{campaign.campaign_name}' to {recipients.count()} recipients")
        
        # Create SMTP connection (shared for all emails in this batch)
        smtp_connection = create_smtp_connection()
        
        sent_count = 0
        failed_count = 0
        
        try:
            # Send each email
            for recipient in recipients:
                try:
                    send_email_direct(recipient.id, smtp_connection)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to send email to recipient {recipient.id}: {str(e)}")
                    failed_count += 1
                    
                    # Mark as failed
                    recipient.status = 'failed'
                    recipient.failed_reason = str(e)[:500]
                    recipient.save(update_fields=['status', 'failed_reason'])
        finally:
            # Close connection
            smtp_connection.quit()
        
        # Update campaign status
        if sent_count > 0:
            campaign.status = "sent"
            campaign.sent_at = timezone.now()
            campaign.save(update_fields=['status', 'sent_at', 'updated_at'])
            
            # Update template usage if template exists
            if campaign.template:
                campaign.template.increment_usage()
        
        logger.info(f"✅ Campaign '{campaign.campaign_name}' completed: {sent_count} sent, {failed_count} failed")
        
        return {
            "status": "completed",
            "sent": sent_count,
            "failed": failed_count,
            "total": sent_count + failed_count
        }
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"❌ Campaign {campaign_id} not found")
        return {"error": f"Campaign {campaign_id} not found"}
    except Exception as e:
        logger.error(f"❌ Error in send_campaign_emails: {str(e)}")
        return {"error": str(e)}


# Update this function in tasks.py
def send_email_direct(recipient_id, smtp_connection=None):
    """
    Send email directly using SMTP connection
    """
    try:
        # Get recipient data
        recipient = EmailRecipient.objects.select_related(
            'campaign', 
            'campaign__template',  # Important: join template
            'contact',
            'contact__company'
        ).get(id=recipient_id)
        
        campaign = recipient.campaign
        contact = recipient.contact
        
        # Validate email address
        if not contact.email or '@' not in contact.email:
            raise ValueError(f"Invalid email address: {contact.email}")
        
        # Get email content from campaign (this uses template if available)
        raw_html_content = campaign.get_email_content()
        raw_subject = campaign.get_email_subject()
        
        # Prepare template variables for personalization
        template_vars = {
            'name': contact.client or 'Valued Customer',
            'email': contact.email,
            'company': contact.company.company_name if contact.company else '',
            'job_role': contact.job_role or '',
            'phone': contact.phone or '',
            'location': contact.company.location if contact.company else '',
            'campaign_name': campaign.campaign_name,
            'subject_line': campaign.subject_line,
            'sender_name': campaign.sender_name or '',
            'sender_email': campaign.sender_email or '',
        }
        
        # Merge with campaign's template variables
        if campaign.template_variables:
            template_vars.update(campaign.template_variables)
        
        # Personalize content
        personalized_html = personalize_content(raw_html_content, contact, recipient, template_vars)
        personalized_subject = personalize_content(raw_subject, contact, recipient, template_vars)
        personalized_preview = personalize_content(campaign.preview_text or '', contact, recipient, template_vars)
        
        # Build tracking URLs
        tracking_pixel_url = recipient.tracking_pixel_url()
        unsubscribe_url = f"{settings.DOMAIN}/api/unsubscribe/{recipient.tracking_id}/"
        
        # Render email template with personalized content
        try:
            email_html = render_to_string('email/campaign_email.html', {
                'campaign_name': campaign.campaign_name,
                'preview_text': personalized_preview,
                'subject': personalized_subject,
                'template_content': personalized_html,  # This is the KEY CHANGE
                'tracking_pixel_url': tracking_pixel_url,
                'unsubscribe_url': unsubscribe_url,
                'current_year': datetime.now().year,
                'company_name': campaign.sender_name or 'Our Company',
                'sender_name': campaign.sender_name or 'Our Company',
                'sender_email': campaign.sender_email or settings.DEFAULT_FROM_EMAIL,
                'recipient_name': contact.client or 'Valued Customer',
                'recipient_email': contact.email,
                'is_test': False,
            })
        except Exception as e:
            logger.warning(f"Template rendering failed, using fallback: {str(e)}")
            # Fallback: Use the personalized content directly with basic wrapper
            email_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{personalized_subject}</title>
            </head>
            <body>
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: #f00000;">{campaign.campaign_name}</h1>
                    {personalized_html}
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666;">
                        <p>From: {campaign.sender_name} &lt;{campaign.sender_email}&gt;</p>
                        <p><a href="{unsubscribe_url}" style="color: #667eea;">Unsubscribe</a></p>
                    </div>
                </div>
            </body>
            </html>
            """
        
        # Add tracking pixel if enabled
        if campaign.enable_tracking and campaign.track_opens:
            tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none;" />'
            email_html = email_html.replace('</body>', f'{tracking_pixel}</body>')
        
        # Create plain text version
        plain_text = campaign.get_plain_text_content()
        if not plain_text:
            plain_text = strip_tags(personalized_html)
        
        # Prepare sender info
        from_name = campaign.sender_name or settings.COMPANY_NAME if hasattr(settings, 'COMPANY_NAME') else 'Our Company'
        from_email = campaign.sender_email or settings.DEFAULT_FROM_EMAIL
        from_addr = formataddr((from_name, from_email))
        
        # Create MIME message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = personalized_subject
        msg['From'] = from_addr
        msg['To'] = contact.email
        
        if campaign.reply_to:
            msg['Reply-To'] = campaign.reply_to
        
        # Add custom headers
        if campaign.custom_headers:
            for key, value in campaign.custom_headers.items():
                msg[key] = str(value)
        
        # Attach parts
        msg.attach(MIMEText(plain_text, 'plain'))
        msg.attach(MIMEText(email_html, 'html'))
        
        # Send using SMTP
        if smtp_connection:
            smtp_connection.sendmail(
                from_addr,
                [contact.email],
                msg.as_string()
            )
        else:
            # Create new connection if not provided
            with create_smtp_connection() as conn:
                conn.sendmail(
                    from_addr,
                    [contact.email],
                    msg.as_string()
                )
        
        # Mark as sent
        recipient.status = 'sent'
        recipient.sent_at = timezone.now()
        recipient.save(update_fields=['status', 'sent_at'])
        
        logger.info(f"✅ Email sent successfully to {contact.email}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error sending email to recipient {recipient_id}: {str(e)}")
        raise



# Update personalize_content function to use template variables:
def personalize_content(content, contact, recipient=None, template_vars=None):
    """
    Replace placeholders with actual contact data
    Add tracking to links if recipient provided
    """
    if not content:
        return ""
    
    # Start with standard replacements
    replacements = {
        '{{name}}': contact.client or 'Valued Customer',
        '{{email}}': contact.email or '',
        '{{company}}': contact.company.company_name if contact.company else '',
        '{{job_role}}': contact.job_role or '',
        '{{phone}}': contact.phone or '',
        '{{location}}': contact.company.location if contact.company else '',
    }
    
    # Add template variables if provided (from campaign.template_variables)
    if template_vars:
        for key, value in template_vars.items():
            # Handle both {{key}} and key formats
            replacements[f'{{{{{key}}}}}'] = str(value)
            replacements[f'{{{key}}}'] = str(value)
    
    # Replace all placeholders
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, str(value))
    
    # Add link tracking if recipient exists
    if recipient and hasattr(recipient, 'tracking_id'):
        import re
        
        def add_tracking(match):
            full_tag = match.group(0)
            href = match.group(3) if len(match.groups()) >= 3 else None
            
            if href:
                # Skip special links
                if (href.startswith('mailto:') or 
                    href.startswith('#') or
                    href.startswith('tel:') or
                    'track/click' in href or
                    'unsubscribe' in href):
                    return full_tag
                
                # Create tracked URL
                tracked_url = (
                    f"{settings.DOMAIN}/api/track/click/{recipient.tracking_id}/"
                    f"?url={quote(href)}"
                )
                return full_tag.replace(href, tracked_url)
            
            return full_tag
        
        # Match <a href="..."> tags
        try:
            content = re.sub(
                r'<a\s+([^>]*\s)?href=(["\'])([^"\']*)\2',
                add_tracking,
                content
            )
        except Exception as e:
            logger.warning(f"Could not add link tracking: {str(e)}")
    
    return content


# ========== ALTERNATIVE TASK USING DJANGO'S EMAIL BACKEND ==========
@shared_task(bind=True, max_retries=3)
def send_single_email(self, recipient_id):
    """
    Alternative: Send single email using Django's EmailBackend
    Useful if you want to use Django's built-in email functionality
    """
    try:
        recipient = EmailRecipient.objects.select_related(
            'campaign', 
            'contact', 
            'contact__company'
        ).get(id=recipient_id)
        
        campaign = recipient.campaign
        contact = recipient.contact
        
        # Validate email address
        if not contact.email or not '@' in contact.email:
            logger.error(f"Invalid email for contact {contact.id}")
            recipient.status = 'failed'
            recipient.failed_reason = "Invalid email address"
            recipient.save(update_fields=['status', 'failed_reason'])
            return f"Invalid email for contact {contact.id}"
        
        # Get raw content from campaign
        raw_html_content = campaign.get_email_content()
        raw_subject = campaign.get_email_subject()
        
        # Personalize content for this contact
        personalized_html = personalize_content(raw_html_content, contact, recipient)
        personalized_subject = personalize_content(raw_subject, contact, recipient)
        
        # Build tracking URLs
        tracking_pixel_url = recipient.tracking_pixel_url()
        unsubscribe_url = f"{settings.DOMAIN}/api/unsubscribe/{recipient.tracking_id}/"
        
        # Create email HTML with tracking
        email_html = personalized_html
        
        # Add tracking pixel
        if campaign.enable_tracking and campaign.track_opens:
            tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none;" />'
            email_html += tracking_pixel
        
        # Create plain text version
        plain_text = strip_tags(personalized_html)
        
        # Prepare sender info
        from_email = campaign.sender_email or settings.DEFAULT_FROM_EMAIL
        if campaign.sender_name:
            from_email = f"{campaign.sender_name} <{from_email}>"
        
        # Create email message using Django's EmailMultiAlternatives
        email = EmailMultiAlternatives(
            subject=personalized_subject,
            body=plain_text,
            from_email=from_email,
            to=[contact.email],
            reply_to=[campaign.reply_to] if campaign.reply_to else None,
        )
        
        # Attach HTML version
        email.attach_alternative(email_html, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        # Mark as sent
        recipient.status = 'sent'
        recipient.sent_at = timezone.now()
        recipient.save(update_fields=['status', 'sent_at'])
        
        logger.info(f"✅ Email sent to {contact.email} for campaign '{campaign.campaign_name}'")
        
        # Check if all emails are sent
        check_campaign_completion.delay(campaign.id)
        
        return f"Email sent to {contact.email}"
    
    except EmailRecipient.DoesNotExist:
        logger.error(f"Recipient {recipient_id} not found")
        return f"Recipient {recipient_id} not found"
    
    except Exception as e:
        logger.error(f"❌ Error sending email to recipient {recipient_id}: {str(e)}")
        
        # Update recipient status
        try:
            recipient = EmailRecipient.objects.get(id=recipient_id)
            recipient.status = 'failed'
            recipient.failed_reason = str(e)[:500]
            recipient.save(update_fields=['status', 'failed_reason'])
        except:
            pass
        
        # Retry logic
        try:
            countdown = 60 * (2 ** self.request.retries)  # Exponential backoff
            raise self.retry(exc=e, countdown=countdown)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for recipient {recipient_id}")
            return f"Failed after max retries: {str(e)}"




# ========== CAMPAIGN COMPLETION CHECK ==========
@shared_task
def check_campaign_completion(campaign_id):
    """
    Check if all emails have been sent and update campaign status
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        total = campaign.recipients.count()
        pending = campaign.recipients.filter(status='pending').count()
        sent = campaign.recipients.filter(status='sent').count()
        failed = campaign.recipients.filter(status='failed').count()
        
        # If no pending emails left
        if pending == 0 and total > 0:
            campaign.status = 'sent'
            campaign.sent_at = timezone.now()
            campaign.save(update_fields=['status', 'sent_at', 'updated_at'])
            
            logger.info(
                f"✅ Campaign '{campaign.campaign_name}' completed: "
                f"{sent} sent, {failed} failed out of {total} total"
            )
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")



# ========== TEST EMAIL TASKS ==========
@shared_task
def send_test_emails_multiple(campaign_id, test_emails):
    """
    Send test emails with campaign preview
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        results = []
        for email in test_emails:
            try:
                # Get content
                html_content = campaign.get_email_content() or ""
                subject = campaign.get_email_subject()
                preview_text = campaign.preview_text or ""
                
                # Create dummy contact for personalization
                class DummyContact:
                    client = "Test User"
                    email = email
                    job_role = "Test Role"
                    phone = "+1234567890"
                    company = None
                
                dummy_contact = DummyContact()
                
                # Personalize with test data
                personalized_html = personalize_content(html_content, dummy_contact, None)
                personalized_subject = personalize_content(subject, dummy_contact, None)
                preview_text = personalize_content(preview_text, dummy_contact, None)
                
                # Create test banner
                test_banner = f"""
                <div style="background: #fff3cd; padding: 20px; margin-bottom: 30px; 
                            border-left: 4px solid #ffc107; border-radius: 4px;">
                    <h3 style="margin: 0 0 10px 0; color: #856404; font-size: 18px;">
                        ⚠️ TEST EMAIL - NOT A REAL CAMPAIGN
                    </h3>
                    <p style="margin: 0; color: #856404; font-size: 14px;">
                        Campaign: <strong>{campaign.campaign_name}</strong><br>
                        Test recipient: <strong>{email}</strong><br>
                        Tracking is disabled in test mode.
                    </p>
                </div>
                """
                
                # Combine test banner with content
                full_content = test_banner + personalized_html
                
                # Try to use template file
                try:
                    email_html = render_to_string('email/campaign_email.html', {
                        'campaign_name': f"[TEST] {campaign.campaign_name}",
                        'preview_text': preview_text,
                        'subject': f"[TEST] {personalized_subject}",
                        'content': full_content,
                        'tracking_pixel_url': '#',
                        'unsubscribe_url': '#',
                        'current_year': datetime.now().year,
                        'company_name': campaign.sender_name or 'Our Company',
                        'sender_name': campaign.sender_name or 'Our Company',
                        'sender_email': campaign.sender_email or settings.DEFAULT_FROM_EMAIL,
                        'recipient_name': 'Test User',
                        'recipient_email': email,
                        'is_test': True,
                    })
                except:
                    # Fallback to inline template
                    email_html = create_fallback_email_html(
                        campaign=campaign,
                        personalized_html=full_content,
                        personalized_subject=f"[TEST] {personalized_subject}",
                        contact=dummy_contact,
                        tracking_pixel_url='#',
                        unsubscribe_url='#'
                    )
                
                plain_text = strip_tags(full_content)
                
                # Prepare sender
                from_email = campaign.sender_email or settings.DEFAULT_FROM_EMAIL
                if campaign.sender_name:
                    from_email = f"{campaign.sender_name} <{from_email}>"
                
                # Send test email using Django's email backend
                msg = EmailMultiAlternatives(
                    subject=f"[TEST] {personalized_subject}",
                    body=plain_text,
                    from_email=from_email,
                    to=[email],
                )
                msg.attach_alternative(email_html, "text/html")
                msg.send(fail_silently=False)
                
                results.append({
                    'email': email,
                    'status': 'sent',
                    'message': 'Test email sent successfully'
                })
                
                logger.info(f"✅ Test email sent to {email}")
                
            except Exception as e:
                logger.error(f"❌ Failed to send test to {email}: {str(e)}")
                results.append({
                    'email': email,
                    'status': 'failed',
                    'message': str(e)
                })
        
        return {
            'campaign_id': campaign_id,
            'total': len(test_emails),
            'sent': sum(1 for r in results if r['status'] == 'sent'),
            'failed': sum(1 for r in results if r['status'] == 'failed'),
            'results': results
        }
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return {'error': f'Campaign {campaign_id} not found'}
    except Exception as e:
        logger.error(f"Error in test emails: {str(e)}")
        return {'error': str(e)}



# ========== BATCH EMAIL SENDING ==========
@shared_task
def send_batch_emails(campaign_id, recipient_ids):
    """
    Send emails to a batch of recipients
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        recipients = EmailRecipient.objects.filter(
            id__in=recipient_ids,
            campaign=campaign,
            status='pending'
        ).select_related('contact', 'contact__company')
        
        logger.info(f"Starting batch send for campaign '{campaign.campaign_name}' to {recipients.count()} recipients")
        
        # Create SMTP connection for this batch
        smtp_connection = create_smtp_connection()
        
        sent_count = 0
        failed_count = 0
        
        try:
            for recipient in recipients:
                try:
                    send_email_direct(recipient.id, smtp_connection)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send to {recipient.contact.email}: {str(e)}")
                    failed_count += 1
        finally:
            smtp_connection.quit()
        
        logger.info(f"Batch completed: {sent_count} sent, {failed_count} failed")
        
        return {
            "sent": sent_count,
            "failed": failed_count,
            "total": sent_count + failed_count
        }
        
    except Exception as e:
        logger.error(f"Error in batch send: {str(e)}")
        return {"error": str(e)}



# ========== ADMIN TASK HANDLER ==========
@shared_task(name='adminpanel.tasks.send_approval_email')
def handle_admin_approval_email(email, name):
    """Handle misrouted admin tasks"""
    logger.info(f"[API] Admin approval task for {email}")
    
    # You can implement actual email sending here if needed
    # Or just log that the task was received
    
    return f"Handled admin task for {name} ({email})"



# ========== UTILITY FUNCTIONS ==========
def test_email_connection():
    """Test email connection"""
    try:
        connection = create_smtp_connection()
        connection.quit()
        return True, "Email connection successful"
    except Exception as e:
        return False, f"Email connection failed: {str(e)}"



def get_email_stats(campaign_id):
    """Get email statistics for a campaign"""
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        stats = campaign.get_recipients_stats()
        stats.update({
            'campaign_name': campaign.campaign_name,
            'campaign_status': campaign.status,
            'sent_at': campaign.sent_at,
            'scheduled_at': campaign.scheduled_at,
            'template_used': campaign.template.name if campaign.template else None,
        })
        
        return stats
    except Exception as e:
        logger.error(f"Error getting email stats: {str(e)}")
        return {"error": str(e)}
    
    
# ========== SCHEDULED CAMPAIGNS HANDLING ==========
@shared_task
def check_and_send_scheduled_campaigns():
    """
    Celery Beat task to check for scheduled campaigns and send them
    This should run every minute via Celery Beat scheduler
    """
    try:
        now_utc = timezone.now().astimezone(pytz.UTC)
        logger.info(f"Checking scheduled campaigns at {now_utc}")
        
        # Find campaigns that are scheduled and past their scheduled time
        campaigns_to_send = EmailCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now_utc  # Scheduled time has passed
        ).exclude(
            scheduled_at__isnull=True
        )
        
        campaign_count = campaigns_to_send.count()
        
        if campaign_count == 0:
            logger.info("No scheduled campaigns to send")
            return {
                "status": "no_campaigns",
                "message": "No scheduled campaigns to send",
                "checked_at": str(now)
            }
        
        logger.info(f"Found {campaign_count} scheduled campaign(s) to send")
        
        results = []
        for campaign in campaigns_to_send:
            try:
                # Pass campaign ID, not the campaign object
                campaign_result = process_scheduled_campaign.delay(campaign.id)  # Pass ID here
                
                # Get the result (or store task ID for async tracking)
                results.append({
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.campaign_name,
                    "task_id": campaign_result.id,
                    "scheduled_at": str(campaign.scheduled_at),
                    "status": "queued"
                })
                
                logger.info(f"Queued campaign {campaign.id} for processing")
                
            except Exception as e:
                logger.error(f"Error queuing campaign {campaign.id}: {str(e)}")
                results.append({
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.campaign_name,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "status": "processed",
            "total_campaigns": campaign_count,
            "checked_at": str(now),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in check_and_send_scheduled_campaigns: {str(e)}")
        return {"error": str(e), "checked_at": str(timezone.now())}


@shared_task
def process_scheduled_campaign(campaign_id):
    """
    Process a single scheduled campaign
    Can be called directly or from check_and_send_scheduled_campaigns
    """
    try:
        logger.info(f"Processing scheduled campaign with ID: {campaign_id}")
        
        # Get the campaign from the database
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        logger.info(f"Found campaign: {campaign.campaign_name} (ID: {campaign.id})")
        
        # Double-check the campaign is still scheduled
        if campaign.status != 'scheduled':
            logger.warning(f"Campaign {campaign.id} status is {campaign.status}, not 'scheduled'")
            return {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "status": "skipped",
                "reason": f"Status is {campaign.status}, not 'scheduled'"
            }
        
        # Check if scheduled time has passed
        now = timezone.now()
        if campaign.scheduled_at > now:
            logger.warning(f"Campaign {campaign.id} scheduled time not reached yet: {campaign.scheduled_at}")
            return {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "status": "not_yet",
                "scheduled_at": str(campaign.scheduled_at),
                "current_time": str(now)
            }
        
        # Check if campaign is ready to send
        if not campaign.sender_email:
            logger.error(f"Campaign {campaign.id} has no sender email")
            campaign.status = 'failed'
            campaign.save(update_fields=['status', 'updated_at'])
            return {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "status": "failed",
                "reason": "No sender email"
            }
        
        if not campaign.sent_lists.exists():
            logger.error(f"Campaign {campaign.id} has no sent lists")
            campaign.status = 'failed'
            campaign.save(update_fields=['status', 'updated_at'])
            return {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "status": "failed",
                "reason": "No sent lists"
            }
        
        # Check if campaign has content
        email_content = campaign.get_email_content()
        if not email_content:
            logger.error(f"Campaign {campaign.id} has no email content")
            campaign.status = 'failed'
            campaign.save(update_fields=['status', 'updated_at'])
            return {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "status": "failed",
                "reason": "No email content"
            }
        
        # Generate recipients if needed
        if campaign.recipients.count() == 0:
            logger.info(f"Generating recipients for campaign {campaign.id}")
            # Generate recipients synchronously for this task
            generate_recipients_for_campaign(campaign.id)  # Call directly, not .delay()
        
        # Check if there are recipients
        pending_recipients = campaign.recipients.filter(status='pending').count()
        if pending_recipients == 0:
            logger.warning(f"Campaign {campaign.id} has no pending recipients")
            campaign.status = 'failed'
            campaign.save(update_fields=['status', 'updated_at'])
            return {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "status": "failed",
                "reason": "No pending recipients"
            }
        
        # Update campaign status to 'sending'
        campaign.status = 'sending'
        campaign.sent_at = now
        campaign.save(update_fields=['status', 'sent_at', 'updated_at'])
        
        logger.info(f"Starting to send campaign {campaign.id} to {pending_recipients} recipients")
        
        # Start sending emails
        send_task = send_campaign_emails.delay(campaign.id)
        
        return {
            "campaign_id": campaign.id,
            "campaign_name": campaign.campaign_name,
            "status": "started",
            "recipients": pending_recipients,
            "scheduled_at": str(campaign.scheduled_at),
            "started_at": str(now),
            "send_task_id": send_task.id
        }
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return {
            "campaign_id": campaign_id,
            "status": "error",
            "reason": "Campaign not found"
        }
    except Exception as e:
        logger.error(f"Error processing scheduled campaign {campaign_id}: {str(e)}")
        return {
            "campaign_id": campaign_id,
            "status": "error",
            "reason": str(e)
        }


@shared_task
def generate_recipients_for_campaign(campaign_id):
    """
    Generate recipients for a campaign (standalone task)
    Can be called with .delay() for async or directly for sync
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        logger.info(f"Generating recipients for campaign {campaign.id}: {campaign.campaign_name}")
        
        # Get clients from sent lists
        included = Client.objects.filter(
            lists__in=campaign.sent_lists.all()
        ).distinct()
        
        # Exclude clients from do-not-send lists
        excluded = Client.objects.filter(
            lists__in=campaign.do_notsent_lists.all()
        )
        
        # Final recipient list (with valid emails)
        final = included.exclude(id__in=excluded).exclude(
            email__isnull=True
        ).exclude(email='')
        
        # Create recipients
        recipients_created = 0
        recipients_updated = 0
        
        for contact in final:
            # Check if recipient already exists
            existing = EmailRecipient.objects.filter(
                campaign=campaign,
                contact=contact
            ).first()
            
            if existing:
                # Update existing recipient to pending if not already sent
                if existing.status != 'sent':
                    existing.status = 'pending'
                    existing.save(update_fields=['status'])
                    recipients_updated += 1
            else:
                # Create new recipient
                EmailRecipient.objects.create(
                    campaign=campaign,
                    contact=contact,
                    status='pending'
                )
                recipients_created += 1
        
        logger.info(f"Generated {recipients_created} new, updated {recipients_updated} existing recipients for campaign {campaign_id}")
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.campaign_name,
            "new_recipients": recipients_created,
            "updated_recipients": recipients_updated,
            "total_recipients": final.count()
        }
        
    except Exception as e:
        logger.error(f"Error generating recipients for campaign {campaign_id}: {str(e)}")
        raise  # Re-raise to propagate the error


@shared_task
def cleanup_old_campaigns():
    """
    Clean up old campaigns and recipients
    Run this daily via Celery Beat
    """
    try:
        from datetime import timedelta
        
        # Delete failed recipients older than 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        deleted_count = EmailRecipient.objects.filter(
            status='failed',
            created_at__lt=thirty_days_ago
        ).delete()[0]
        
        # Archive old sent campaigns (older than 90 days)
        ninety_days_ago = timezone.now() - timedelta(days=90)
        old_campaigns = EmailCampaign.objects.filter(
            status='sent',
            sent_at__lt=ninety_days_ago
        )
        
        archived_count = 0
        for campaign in old_campaigns:
            campaign.status = 'archived'
            campaign.save(update_fields=['status'])
            archived_count += 1
        
        logger.info(f"Cleanup: Deleted {deleted_count} old failed recipients, archived {archived_count} old campaigns")
        
        return {
            "deleted_failed_recipients": deleted_count,
            "archived_campaigns": archived_count
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_campaigns: {str(e)}")
        return {"error": str(e)}
    


