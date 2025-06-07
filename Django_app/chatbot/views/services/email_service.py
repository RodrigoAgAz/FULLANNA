"""
Email Verification Service for ANNA
Handles email verification for patient authentication
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from django.core.mail import send_mail
from django.conf import settings
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class EmailVerificationService:
    """Service for email verification and notifications"""
    
    def __init__(self):
        # In production, use Redis or database for verification codes
        self.verification_codes: Dict[str, Dict] = {}
        self.code_expiry_minutes = 15
    
    async def send_verification_email(
        self, 
        email: str, 
        patient_name: str = "User"
    ) -> str:
        """Send verification code via email"""
        try:
            # Generate 6-digit code
            code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
            
            # Store with expiration (15 minutes)
            self.verification_codes[email] = {
                'code': code,
                'expires': datetime.now() + timedelta(minutes=self.code_expiry_minutes),
                'attempts': 0
            }
            
            # Prepare email content
            subject = "ANNA Chatbot - Email Verification"
            message = f"""
Hello {patient_name},

Your verification code for ANNA Health Assistant is: {code}

This code will expire in {self.code_expiry_minutes} minutes.

For your security, please do not share this code with anyone.

Best regards,
ANNA Healthcare Team
"""
            
            # Send email asynchronously
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@anna-health.com')
            
            await sync_to_async(send_mail)(
                subject,
                message,
                from_email,
                [email],
                fail_silently=False
            )
            
            logger.info(f"Verification email sent to {email}")
            return code
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise
    
    def verify_code(self, email: str, code: str) -> bool:
        """Verify email code"""
        if email not in self.verification_codes:
            logger.warning(f"No verification code found for {email}")
            return False
        
        stored_data = self.verification_codes[email]
        
        # Check expiration
        if datetime.now() > stored_data['expires']:
            del self.verification_codes[email]
            logger.warning(f"Verification code expired for {email}")
            return False
        
        # Increment attempts
        stored_data['attempts'] += 1
        
        # Check for too many attempts (max 3)
        if stored_data['attempts'] > 3:
            del self.verification_codes[email]
            logger.warning(f"Too many verification attempts for {email}")
            return False
        
        # Verify code
        if stored_data['code'] == code:
            del self.verification_codes[email]
            logger.info(f"Email verification successful for {email}")
            return True
        
        logger.warning(f"Invalid verification code for {email}")
        return False
    
    def resend_code(self, email: str) -> bool:
        """Check if code can be resent (prevent spam)"""
        if email not in self.verification_codes:
            return True
        
        stored_data = self.verification_codes[email]
        time_since_sent = datetime.now() - (stored_data['expires'] - timedelta(minutes=self.code_expiry_minutes))
        
        # Allow resend after 2 minutes
        return time_since_sent.total_seconds() > 120
    
    async def send_welcome_email(
        self,
        email: str,
        patient_name: str = "User"
    ) -> bool:
        """Send welcome email after successful verification"""
        try:
            subject = "Welcome to ANNA Health Assistant"
            message = f"""
Hello {patient_name},

Welcome to ANNA, your AI-powered health assistant!

You can now:
• Schedule and manage appointments
• Access your medical records
• Get health information and guidance
• Receive medication reminders
• Ask health-related questions

Your privacy and data security are our top priorities. All communications are HIPAA-compliant.

Start chatting with ANNA anytime to manage your health!

Best regards,
ANNA Healthcare Team
"""
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@anna-health.com')
            
            await sync_to_async(send_mail)(
                subject,
                message,
                from_email,
                [email],
                fail_silently=False
            )
            
            logger.info(f"Welcome email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Welcome email error: {e}")
            return False
    
    async def send_password_reset_email(
        self,
        email: str,
        reset_link: str,
        patient_name: str = "User"
    ) -> bool:
        """Send password reset email"""
        try:
            subject = "ANNA Health Assistant - Password Reset"
            message = f"""
Hello {patient_name},

You requested a password reset for your ANNA Health Assistant account.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour for your security.

If you didn't request this reset, please ignore this email.

Best regards,
ANNA Healthcare Team
"""
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@anna-health.com')
            
            await sync_to_async(send_mail)(
                subject,
                message,
                from_email,
                [email],
                fail_silently=False
            )
            
            logger.info(f"Password reset email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Password reset email error: {e}")
            return False
    
    def cleanup_expired_codes(self):
        """Clean up expired verification codes"""
        expired_emails = []
        now = datetime.now()
        
        for email, data in self.verification_codes.items():
            if now > data['expires']:
                expired_emails.append(email)
        
        for email in expired_emails:
            del self.verification_codes[email]
        
        if expired_emails:
            logger.info(f"Cleaned up {len(expired_emails)} expired verification codes")

# Global instance
email_service = EmailVerificationService()

# Convenience functions
async def send_verification_email(email: str, patient_name: str = "User") -> str:
    return await email_service.send_verification_email(email, patient_name)

def verify_email_code(email: str, code: str) -> bool:
    return email_service.verify_code(email, code)

async def send_welcome_email(email: str, patient_name: str = "User") -> bool:
    return await email_service.send_welcome_email(email, patient_name)

async def send_password_reset_email(email: str, reset_link: str, patient_name: str = "User") -> bool:
    return await email_service.send_password_reset_email(email, reset_link, patient_name)