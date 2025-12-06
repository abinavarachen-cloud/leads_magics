# services/email_builder.py
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from urllib.parse import quote
import logging
from typing import List, Dict, Optional
from .models import EmailCampaign, EmailRecipient, Client

logger = logging.getLogger(__name__)


class EmailBuilder:
    """
    Service class to build complete email messages with proper headers and tracking
    """
    
    @staticmethod
    def build_email(campaign: EmailCampaign, recipient: EmailRecipient) -> Dict:
        """
        Build complete email message for a recipient
        
        Returns:
            Dictionary with email components:
            {
                'subject': str,
                'from_email': str,
                'to': [str],
                'cc': [str],
                'bcc': [str],
                'html_content': str,
                'plain_text': str,
                'headers': dict,
                'reply_to': str
            }
        """
        contact = recipient.contact
        
        # 1. Build sender string
        from_email = EmailBuilder._build_sender_address(campaign)
        
        # 2. Build recipient lists
        to_email = [contact.email] if contact.email else []
        cc_emails = EmailBuilder._get_emails_from_lists(campaign.cc_lists.all())
        bcc_emails = EmailBuilder._get_emails_from_lists(campaign.bcc_lists.all())
        
        # 3. Build subject with personalization
        subject = EmailBuilder._personalize_content(
            campaign.subject_line or "No Subject",
            contact,
            recipient
        )
        
        # 4. Build email body
        html_content = EmailBuilder._build_html_body(campaign, contact, recipient)
        plain_text = EmailBuilder._build_plain_text_body(campaign, contact)
        
        # 5. Build headers
        headers = EmailBuilder._build_email_headers(campaign, recipient)
        
        return {
            'subject': subject,
            'from_email': from_email,
            'to': to_email,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'html_content': html_content,
            'plain_text_content': plain_text,
            'headers': headers,
            'reply_to': campaign.reply_to or campaign.sender_email
        }
    
    @staticmethod
    def _build_sender_address(campaign: EmailCampaign) -> str:
        """Build proper sender address format"""
        if campaign.sender_name:
            return f"{campaign.sender_name} <{campaign.sender_email}>"
        return campaign.sender_email
    
    @staticmethod
    def _get_emails_from_lists(lists) -> List[str]:
        """Extract all unique emails from lists"""
        emails = set()
        for list_obj in lists:
            for client in list_obj.clients.all():
                if client.email:
                    emails.add(client.email)
        return list(emails)
    
    @staticmethod
    def _personalize_content(content: str, contact: Client, recipient: Optional[EmailRecipient] = None) -> str:
        """Personalize content with contact data"""
        if not content:
            return ""
        
        replacements = {
            '{{name}}': contact.client or 'Valued Customer',
            '{{first_name}}': contact.client.split()[0] if contact.client else 'Customer',
            '{{email}}': contact.email or '',
            '{{company}}': contact.company.company_name if contact.company else '',
            '{{job_role}}': contact.job_role or '',
            '{{phone}}': contact.phone or '',
            '{{location}}': contact.company.location if contact.company else '',
            '{{tracking_id}}': str(recipient.tracking_id) if recipient else '',
        }
        
        personalized = content
        for placeholder, value in replacements.items():
            personalized = personalized.replace(placeholder, str(value))
        
        return personalized
    
    @staticmethod
    def _build_html_body(campaign: EmailCampaign, contact: Client, recipient: EmailRecipient) -> str:
        """Build complete HTML email body with tracking"""
        
        # Get base content
        if campaign.custom_content:
            base_content = campaign.custom_content
        elif campaign.template:
            rendered = campaign.template.render_template(campaign.template_variables or {})
            base_content = rendered['html_content']
        else:
            base_content = ""
        
        # Personalize base content
        personalized_content = EmailBuilder._personalize_content(base_content, contact, recipient)
        
        # Add tracking pixel if enabled
        tracking_pixel = ""
        if campaign.enable_tracking and campaign.track_opens:
            tracking_pixel = f'<img src="{recipient.tracking_pixel_url()}" width="1" height="1" alt="" style="display:none;">'
        
        # Add campaign info header
        campaign_info = f"""
        <div style="background:#f8f9fa; padding:15px; margin-bottom:20px; border-left:4px solid #007bff;">
            <h3 style="margin:0 0 10px 0; color:#333; font-size:18px;">{campaign.campaign_name}</h3>
            <p style="margin:0; color:#666; font-size:14px;">{campaign.preview_text or ''}</p>
        </div>
        """
        
        # Render complete email template
        context = {
            'campaign_name': campaign.campaign_name,
            'preview_text': campaign.preview_text,
            'content': personalized_content,
            'tracking_pixel': tracking_pixel,
            'unsubscribe_url': f"{settings.DOMAIN}/api/unsubscribe/{recipient.tracking_id}/",
            'contact_email': contact.email,
            'current_year': datetime.now().year,
        }
        
        return render_to_string('email_templates/campaign_email.html', context)
    
    @staticmethod
    def _build_plain_text_body(campaign: EmailCampaign, contact: Client) -> str:
        """Build plain text version"""
        if campaign.email_format in ['text', 'both']:
            if campaign.custom_content:
                content = strip_tags(campaign.custom_content)
            elif campaign.template:
                rendered = campaign.template.render_template(campaign.template_variables or {})
                content = rendered.get('plain_text_content', '')
            else:
                content = ""
            
            # Add campaign info
            campaign_info = f"""
            {campaign.campaign_name}
            {campaign.preview_text or ''}
            
            """
            
            personalized = EmailBuilder._personalize_content(content, contact)
            return campaign_info + personalized
        
        return ""
    
    @staticmethod
    def _build_email_headers(campaign: EmailCampaign, recipient: EmailRecipient) -> Dict:
        """Build email headers for tracking"""
        headers = {}
        
        # Add custom headers
        headers.update(campaign.custom_headers or {})
        
        # Add tracking headers
        if campaign.enable_tracking:
            headers['X-Campaign-ID'] = str(campaign.id)
            headers['X-Recipient-ID'] = str(recipient.id)
            headers['X-Tracking-ID'] = str(recipient.tracking_id)
            
            # For email clients that support List-Unsubscribe
            headers['List-Unsubscribe'] = f'<{settings.DOMAIN}/api/unsubscribe/{recipient.tracking_id}/>'
            headers['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
        
        return headers
    
    @staticmethod
    def _add_tracking_to_links(html_content: str, recipient: EmailRecipient, campaign: EmailCampaign) -> str:
        """Add tracking to all links in HTML content"""
        if not campaign.enable_tracking or not campaign.track_clicks:
            return html_content
        
        import re
        
        def replace_link(match):
            full_tag = match.group(0)
            href = match.group(1)
            
            # Skip special links
            if not href or href.startswith(('mailto:', '#', 'javascript:')):
                return full_tag
            
            # Skip if already tracked
            if 'track/click' in href:
                return full_tag
            
            # Create tracked URL
            tracked_url = f"{settings.DOMAIN}/api/track/click/{recipient.tracking_id}/?url={quote(href)}"
            
            # Replace href in the tag
            return full_tag.replace(f'"{href}"', f'"{tracked_url}"')
        
        # Match href attributes
        pattern = r'<a\s+[^>]*href="([^"]*)"[^>]*>'
        return re.sub(pattern, replace_link, html_content)