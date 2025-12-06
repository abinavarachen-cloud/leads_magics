import ssl
import smtplib
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend

class CustomEmailBackend(SMTPBackend):
    """Custom email backend that handles SSL certificate issues"""
    
    def open(self):
        """
        Opens the connection to the email server.
        Returns True if successful.
        """
        if self.connection:
            return False
        
        try:
            # Create SSL context that doesn't verify certificates
            context = ssl._create_unverified_context()
            
            # For Gmail with TLS
            self.connection = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            
            # Send EHLO
            self.connection.ehlo()
            
            # Start TLS with unverified context
            if self.use_tls:
                self.connection.starttls(context=context)
                self.connection.ehlo()  # Re-ehlo after TLS
            
            # Login if credentials provided
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            
            return True
            
        except Exception as e:
            # Log the error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Email connection error: {str(e)}")
            
            if not self.fail_silently:
                raise
            return False
        
        
        
        