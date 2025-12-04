import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leads_magics.settings')
django.setup()

from django.core.mail import send_mail

# Test email sending directly
print("Testing email configuration...")
try:
    send_mail(
        subject='Test Email',
        message='This is a test email from Django.',
        from_email='test@example.com',
        recipient_list=['your-email@example.com'],
        fail_silently=False,
    )
    print("✓ Test email sent successfully!")
except Exception as e:
    print(f"✗ Error sending test email: {str(e)}")