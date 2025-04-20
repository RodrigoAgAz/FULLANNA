from celery import shared_task
from chatbot.views.services.fhir_service import get_fhir_client
from chatbot.views.services.preventive_care_reminder_service import PreventiveCareReminderService, send_sms
from chatbot.views.services.medication_service import MedicationAdherenceReminderService
from chatbot.views.services.post_discharge_service import send_post_discharge_reminders
import logging
import redis_lock
import redis
from django.conf import settings
from audit.utils import log_event

logger = logging.getLogger('chatbot')

# Initialize Redis client for locks - use REDIS_URL from settings
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)

@shared_task
def process_preventive_care_reminders():
    """
    Process preventive care reminders for eligible patients.
    Uses Redis lock to prevent concurrent execution.
    """
    # Use Redis lock to ensure only one instance runs at a time
    lock_name = "task-process_preventive_care_reminders"
    logger.info(f"Attempting to acquire lock for {lock_name}")
    
    with redis_lock.Lock(redis_client, lock_name, expire=300):
        logger.info(f"Lock acquired for {lock_name}")
        try:
            fhir_client = get_fhir_client()
            reminder_service = PreventiveCareReminderService(fhir_client, send_sms)
            reminder_count = reminder_service.process_reminders()
            logger.info(f"Preventive care reminders processed successfully: {reminder_count} reminders sent")
            
            # Audit successful execution
            log_event(
                actor="system",
                action="preventive_care_reminders.processed",
                resource="preventive_care_task",
                meta={"count": reminder_count}
            )
        except Exception as e:
            logger.error(f"Error processing preventive care reminders: {e}")
            # Audit the error
            log_event(
                actor="system",
                action="preventive_care_reminders.error",
                resource="preventive_care_task",
                meta={"error_message": str(e)}
            )
    logger.info(f"Lock released for {lock_name}")

@shared_task
def process_medication_reminders_task():
    """
    Celery task to process medication adherence and refill reminders.
    This task instantiates the service and runs the process_medication_reminders() method.
    Uses Redis lock to prevent concurrent execution.
    """
    lock_name = "task-process_medication_reminders"
    logger.info(f"Attempting to acquire lock for {lock_name}")
    
    with redis_lock.Lock(redis_client, lock_name, expire=300):
        logger.info(f"Lock acquired for {lock_name}")
        try:
            fhir_client = get_fhir_client()
            reminder_service = MedicationAdherenceReminderService(fhir_client, send_sms)
            sent_count = reminder_service.process_medication_reminders()
            logger.info(f"Medication reminders processed successfully: {sent_count} reminders sent")
            
            # Audit successful execution
            log_event(
                actor="system",
                action="medication_reminders.processed",
                resource="medication_reminder_task",
                meta={"count": sent_count}
            )
        except Exception as e:
            logger.error(f"Error processing medication reminders: {e}")
            # Audit the error
            log_event(
                actor="system",
                action="medication_reminders.error",
                resource="medication_reminder_task",
                meta={"error_message": str(e)}
            )
    logger.info(f"Lock released for {lock_name}")

@shared_task
def send_post_discharge_reminders_task():
    """
    Celery task to send follow-up messages to patients recently discharged.
    Uses Redis lock to prevent concurrent execution.
    """
    lock_name = "task-send_post_discharge_reminders"
    logger.info(f"Attempting to acquire lock for {lock_name}")
    
    with redis_lock.Lock(redis_client, lock_name, expire=300):
        logger.info(f"Lock acquired for {lock_name}")
        try:
            reminder_count = send_post_discharge_reminders()
            logger.info(f"Post-discharge reminders sent successfully: {reminder_count} reminders")
            
            # Audit successful execution
            log_event(
                actor="system",
                action="post_discharge_reminders.processed",
                resource="post_discharge_task",
                meta={"count": reminder_count}
            )
        except Exception as e:
            logger.error(f"Error sending post-discharge reminders: {e}")
            # Audit the error
            log_event(
                actor="system",
                action="post_discharge_reminders.error",
                resource="post_discharge_task",
                meta={"error_message": str(e)}
            )
    logger.info(f"Lock released for {lock_name}")