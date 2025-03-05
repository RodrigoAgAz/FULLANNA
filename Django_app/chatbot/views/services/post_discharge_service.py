# chatbot/views/services/post_discharge_service.py
from celery import shared_task
from django.conf import settings
from twilio.rest import Client
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from chatbot.views.services.fhir_service import FHIRService  # Adjust import as per your project structure
print ("33")
logger = logging.getLogger('chatbot')
 
@shared_task
async def send_post_discharge_reminders():
    """
    Identifies patients discharged 72 hours ago and sends reminders.
    """
    try:
        fhir_service = FHIRService()
        current_time = datetime.now(ZoneInfo("UTC"))
        reminder_time = current_time - timedelta(hours=72)
        reminder_time_iso = reminder_time.isoformat()
 
        # Search for Encounters that have ended 72 hours ago
        encounters = await fhir_service.search(
            resource_type='Encounter',
            params={
                'status': 'finished',
                'end': f"eq{reminder_time_iso}",
                '_sort': '-end'
            }
        )
 
        if not encounters or 'entry' not in encounters:
            logger.info("No discharged patients found for reminder.")
            return
 
        for entry in encounters['entry']:
            encounter = entry['resource']
            patient_ref = encounter.get('subject', {}).get('reference', '')
            patient_id = patient_ref.split('/')[-1] if '/' in patient_ref else None
 
            if not patient_id:
                logger.warning("Encounter without patient reference.")
                continue
 
            # Retrieve patient details
            patient = await fhir_service.read('Patient', patient_id)
            if not patient:
                logger.warning(f"Patient {patient_id} not found.")
                continue
 
            patient_phone = fhir_service.get_patient_phone(patient)
            if not patient_phone:
                logger.warning(f"No phone number for patient {patient_id}.")
                continue
 
            patient_name = fhir_service.get_patient_name(patient)
 
            # Send SMS reminder
            success = await send_sms_reminder(patient_phone, patient_name)
            if success:
                logger.info(f"Reminder sent to patient {patient_id} for encounter {encounter['id']}.")
            else:
                logger.error(f"Failed to send reminder to patient {patient_id} for encounter {encounter['id']}.")
 
    except Exception as e:
        logger.error(f"Error in send_post_discharge_reminders: {str(e)}", exc_info=True)
        
async def send_sms_reminder(to_number, patient_name):
    """
    Sends an SMS reminder via Twilio.
    """
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message_body = (
            f"Hello {patient_name},\n\n"
            "We hope you're recovering well after your recent discharge. "
            "Please reply with how you're feeling today, or type 'help' if you have any concerns.\n\n"
            "Your Healthcare Team"
        )
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_number
        )
        logger.info(f"Sent SMS to {to_number}: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Error sending SMS to {to_number}: {str(e)}", exc_info=True)
        return False
print ("34")