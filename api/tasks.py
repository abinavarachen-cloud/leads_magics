from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from .models import EmailCampaign, EmailRecipient, Client
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_campaign_emails(campaign_id):
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        # Get all pending recipients
        recipients = campaign.recipients.filter(status='pending')
        
        logger.info(f"Starting to send campaign '{campaign.campaign_name}' to {recipients.count()} recipients")
        
        # Send email to each recipient
        for recipient in recipients:
            send_single_email.delay(recipient.id)
        
        return f"Queued {recipients.count()} emails for sending"
    
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return f"Campaign {campaign_id} not found"
    except Exception as e:
        logger.error(f"Error sending campaign {campaign_id}: {str(e)}")
        return f"Error: {str(e)}"


@shared_task(bind=True, max_retries=3)
def send_single_email(self, recipient_id):
    try:
        recipient = EmailRecipient.objects.select_related('campaign', 'contact').get(id=recipient_id)
        campaign = recipient.campaign
        contact = recipient.contact
        
        # Prepare email content
        subject = campaign.get_email_subject()
        html_content = campaign.get_email_content()
        
        # Add tracking pixel to HTML content
        tracking_pixel = f'<img src="{recipient.tracking_pixel_url()}" width="1" height="1" style="display:none;" />'
        html_content_with_tracking = html_content + tracking_pixel
        
        # Personalize content (replace placeholders)
        html_content_with_tracking = personalize_content(html_content_with_tracking, contact)
        subject = personalize_content(subject, contact)
        
        # Create plain text version
        text_content = strip_tags(html_content)
        
        # Prepare sender info
        from_email = f"{campaign.sender_name} <{campaign.sender_email}>" if campaign.sender_name else campaign.sender_email
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[contact.email],
        )
        email.attach_alternative(html_content_with_tracking, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        # Mark as sent
        recipient.mark_sent(when=timezone.now())
        
        logger.info(f"Email sent successfully to {contact.email} for campaign {campaign.campaign_name}")
        
        return f"Email sent to {contact.email}"
    
    except EmailRecipient.DoesNotExist:
        logger.error(f"Recipient {recipient_id} not found")
        return f"Recipient {recipient_id} not found"
    
    except Exception as e:
        logger.error(f"Error sending email to recipient {recipient_id}: {str(e)}")
        
        # Update recipient status to failed
        try:
            recipient = EmailRecipient.objects.get(id=recipient_id)
            recipient.status = 'failed'
            recipient.failed_reason = str(e)
            recipient.save(update_fields=['status', 'failed_reason'])
        except:
            pass
        
        # Retry the task
        try:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for recipient {recipient_id}")
            return f"Failed after max retries: {str(e)}"


@shared_task
def send_test_email(campaign_id, test_email):
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        # Prepare email content
        subject = f"[TEST] {campaign.get_email_subject()}"
        html_content = campaign.get_email_content()
        text_content = strip_tags(html_content)
        
        # Add test notice
        test_notice = "<div style='background: #fff3cd; padding: 10px; margin-bottom: 20px; border: 1px solid #ffc107;'><strong>⚠️ This is a TEST email</strong></div>"
        html_content = test_notice + html_content
        
        # Prepare sender info
        from_email = f"{campaign.sender_name} <{campaign.sender_email}>" if campaign.sender_name else campaign.sender_email
        
        # Create and send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[test_email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f"Test email sent successfully to {test_email} for campaign {campaign.campaign_name}")
        
        return f"Test email sent to {test_email}"
    
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def send_test_emails_multiple(campaign_id, test_emails):
    """
    Send test emails to multiple recipients
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        results = []
        for email in test_emails:
            try:
                # Prepare email content
                subject = f"[TEST] {campaign.get_email_subject()}"
                html_content = campaign.get_email_content() or ""
                text_content = strip_tags(html_content)
                
                # Add test notice
                test_notice = """
                <div style="background: #fff3cd; padding: 10px; margin-bottom: 20px; 
                            border: 1px solid #ffc107; border-radius: 5px;">
                    <strong>⚠️ TEST EMAIL - NOT A REAL CAMPAIGN</strong><br>
                    <small>Recipient: {email}</small>
                </div>
                """.format(email=email)
                
                html_content = test_notice + html_content
                
                # Personalize with test data
                html_content = html_content.replace('{{name}}', 'Test User')
                html_content = html_content.replace('{{email}}', email)
                subject = subject.replace('{{name}}', 'Test User')
                
                # Prepare sender info
                from_email = f"{campaign.sender_name} <{campaign.sender_email}>" if campaign.sender_name else campaign.sender_email
                
                # Create and send email
                email_msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=from_email,
                    to=[email],
                )
                email_msg.attach_alternative(html_content, "text/html")
                email_msg.send(fail_silently=False)
                
                results.append({
                    'email': email,
                    'status': 'sent',
                    'message': 'Email sent successfully'
                })
                
                logger.info(f"Test email sent successfully to {email} for campaign {campaign.campaign_name}")
                
            except Exception as e:
                logger.error(f"Failed to send test email to {email}: {str(e)}")
                results.append({
                    'email': email,
                    'status': 'failed',
                    'message': str(e)
                })
        
        return {
            'campaign_id': campaign_id,
            'total': len(test_emails),
            'sent': len([r for r in results if r['status'] == 'sent']),
            'failed': len([r for r in results if r['status'] == 'failed']),
            'results': results
        }
        
    except EmailCampaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return {'error': f'Campaign {campaign_id} not found'}
    except Exception as e:
        logger.error(f"Error sending test emails: {str(e)}")
        return {'error': str(e)} 
    
    

def personalize_content(content, contact):
    """Helper function to personalize email content"""
    replacements = {
        '{{name}}': contact.client or 'Valued Customer',
        '{{email}}': contact.email or '',
        '{{company}}': contact.company.company_name if contact.company else '',
        '{{job_role}}': contact.job_role or '',
        '{{phone}}': contact.phone or '',
    }
    
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    
    return content


# Dummy task to handle adminpanel.tasks.send_approval_email calls
@shared_task(name='adminpanel.tasks.send_approval_email')
def handle_admin_approval_email(email, name):
    """Handle admin approval email tasks sent to wrong queue"""
    print(f"[API] Received admin approval task for {email}")
    return f"Dummy approval email task executed for {name} <{email}>"


