from celery import shared_task
from chatbot.views.services.fhir_service import get_fhir_client
from chatbot.views.services.preventive_care_reminder_service import PreventiveCareReminderService, send_sms
import logging

logger = logging.getLogger('chatbot')

@shared_task
def process_preventive_care_reminders():
    try:
        fhir_client = get_fhir_client()
        reminder_service = PreventiveCareReminderService(fhir_client, send_sms)
        reminder_service.process_reminders()
        logger.info("Preventive care reminders processed successfully.")
    except Exception as e:
        logger.error(f"Error processing preventive care reminders: {e}")
# chatbot/tasks.py
from celery import shared_task
from chatbot.views.services.medication_service import (
    MedicationAdherenceReminderService,
    get_fhir_client,
    send_sms,
)

@shared_task
def process_medication_reminders_task():
    """
    Celery task to process medication adherence and refill reminders.
    This task instantiates the service and runs the process_medication_reminders() method.
    """
    fhir_client = get_fhir_client()
    reminder_service = MedicationAdherenceReminderService(fhir_client, send_sms)
    reminder_service.process_medication_reminders()
