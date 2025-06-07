"""
Notification Service for ANNA
Handles SMS notifications via Twilio
"""

import logging
from typing import Optional
from django.conf import settings
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications via SMS"""
    
    def __init__(self):
        self.twilio_client = None
        self._initialize_twilio()
    
    def _initialize_twilio(self):
        """Initialize Twilio client"""
        try:
            twilio_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            twilio_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            
            if twilio_sid and twilio_token:
                from twilio.rest import Client
                self.twilio_client = Client(twilio_sid, twilio_token)
                logger.info("Twilio client initialized successfully")
            else:
                logger.warning("Twilio credentials not configured - SMS notifications disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            self.twilio_client = None
    
    async def send_sms(self, to_number: str, message: str) -> bool:
        """Send SMS message asynchronously"""
        if not self.twilio_client:
            logger.warning("Twilio not configured - cannot send SMS")
            return False
        
        try:
            # Use sync_to_async to make Twilio call async
            result = await sync_to_async(self._send_sms_sync)(to_number, message)
            return result
        except Exception as e:
            logger.error(f"Async SMS send error: {e}")
            return False
    
    def _send_sms_sync(self, to_number: str, message: str) -> bool:
        """Synchronous SMS sending"""
        try:
            twilio_phone = getattr(settings, 'TWILIO_PHONE_NUMBER', None)
            if not twilio_phone:
                logger.error("TWILIO_PHONE_NUMBER not configured")
                return False
            
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=twilio_phone,
                to=to_number
            )
            logger.info(f"SMS sent successfully: {message_obj.sid}")
            return True
        except Exception as e:
            logger.error(f"Twilio error: {e}")
            return False
    
    async def send_appointment_reminder(
        self, 
        to_number: str, 
        appointment_datetime: str,
        provider_name: str = "your healthcare provider"
    ) -> bool:
        """Send appointment reminder SMS"""
        message = (
            f"📅 Appointment Reminder: You have an appointment with {provider_name} "
            f"on {appointment_datetime}. Reply 'CONFIRM' to confirm or 'RESCHEDULE' if you need to reschedule."
        )
        return await self.send_sms(to_number, message)
    
    async def send_medication_reminder(
        self,
        to_number: str,
        medication_name: str,
        dosage: Optional[str] = None
    ) -> bool:
        """Send medication reminder SMS"""
        message = f"💊 Medication Reminder: Time to take your {medication_name}"
        if dosage:
            message += f" ({dosage})"
        message += ". Reply 'TAKEN' when done."
        
        return await self.send_sms(to_number, message)
    
    async def send_lab_results_notification(
        self,
        to_number: str,
        test_name: str = "lab results"
    ) -> bool:
        """Send lab results available notification"""
        message = (
            f"🔬 Lab Results Available: Your {test_name} results are now available. "
            "Contact ANNA to review them or log into your patient portal."
        )
        return await self.send_sms(to_number, message)
    
    async def send_emergency_alert(
        self,
        to_number: str,
        patient_name: str = "Patient"
    ) -> bool:
        """Send emergency alert SMS"""
        message = (
            f"🚨 EMERGENCY ALERT: {patient_name} has indicated they need emergency medical attention. "
            "Please contact them immediately or call emergency services if you cannot reach them."
        )
        return await self.send_sms(to_number, message)

# Global instance
notification_service = NotificationService()

# Convenience functions
async def send_sms(to_number: str, message: str) -> bool:
    return await notification_service.send_sms(to_number, message)

async def send_appointment_reminder(to_number: str, appointment_datetime: str, provider_name: str = "your healthcare provider") -> bool:
    return await notification_service.send_appointment_reminder(to_number, appointment_datetime, provider_name)

async def send_medication_reminder(to_number: str, medication_name: str, dosage: Optional[str] = None) -> bool:
    return await notification_service.send_medication_reminder(to_number, medication_name, dosage)

async def send_lab_results_notification(to_number: str, test_name: str = "lab results") -> bool:
    return await notification_service.send_lab_results_notification(to_number, test_name)

async def send_emergency_alert(to_number: str, patient_name: str = "Patient") -> bool:
    return await notification_service.send_emergency_alert(to_number, patient_name)