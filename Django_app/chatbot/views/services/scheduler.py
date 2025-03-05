from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from chatbot.views.utils.shared import get_resource_name 
import dateparser
from django.conf import settings
from ..config import config as app_config
import logging
import openai
from celery import shared_task
from celery.schedules import crontab
from .medication_service import MedicationAdherenceReminderService
from ..utils.datetime_utils import get_current_time
openai.api_key = settings.OPENAI_API_KEY

fhir_client = app_config.get_fhir_client()
# Configure logging
logger = logging.getLogger('chatbot')

# Initialize FHIR Client


# Initialize OpenAI client
client = settings.OPENAI_API_KEY

print ("36")

class ScheduleManager:
    def __init__(self, fhir_client, logger=None):
        self.fhir_client = fhir_client
        self.logger = logger or logging.getLogger(__name__)

    def create_unlimited_schedule(self, practitioner_id):
        """Creates a schedule with an extended planning horizon"""
        schedule = {
            "resourceType": "Schedule",
            "active": True,
            "serviceCategory": [{"text": "Consultation"}],
            "actor": [{
                "reference": f"Practitioner/{practitioner_id}",
                "type": "Practitioner"
            }],
            "planningHorizon": {
                "start": "2024-01-01T00:00:00Z",
                "end": "2050-12-31T23:59:59Z"
            }
        }
        return self.fhir_client.create("Schedule", schedule)

    def update_all_schedules(self):
        """Updates all existing schedules with unlimited planning horizon"""
        results = {"success": 0, "failed": 0}
        schedules = self.fhir_client.search("Schedule", {})
        
        if not schedules or 'entry' not in schedules:
            self.logger.warning("No schedules found to update")
            return results

        for entry in schedules.get('entry', []):
            schedule = entry.get('resource', {})
            schedule_id = schedule.get('id')
            try:
                schedule['planningHorizon'] = {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2050-12-31T23:59:59Z"
                }
                if self.fhir_client.update("Schedule", schedule_id, schedule):
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                results["failed"] += 1
                self.logger.error(f"Error updating schedule {schedule_id}: {str(e)}")

        return results

    def create_slots(self, schedule_id, start_date="2024-01-01", end_date="2050-12-31"):
        """Creates slots for a given schedule between start and end dates"""
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            current = start
            
            while current < end:
                if 9 <= current.hour < 17:  # Business hours
                    slot = {
                        "resourceType": "Slot",
                        "schedule": {"reference": f"Schedule/{schedule_id}"},
                        "status": "free",
                        "start": current.isoformat() + 'Z',
                        "end": (current + timedelta(minutes=30)).isoformat() + 'Z'
                    }
                    self.fhir_client.create("Slot", slot)
                
                current += timedelta(minutes=30)
                
            return {"status": "success", "message": "Slots created successfully"}
        except Exception as e:
            self.logger.error(f"Error creating slots: {str(e)}")
            return {"status": "error", "message": str(e)}

# Initialize Schedule Manager
def search_available_slots(practitioner_id, datetime_requested):
    """Search for available slots for a practitioner at a specific time"""
    try:
        logger.info(f"Searching for slots for practitioner {practitioner_id} at {datetime_requested}")
        
        fhir_client = app_config.get_fhir_client()
        if not fhir_client:
            logger.error("FHIR client is None")
            return []
            
        # First, get or create the schedule
        schedule_search = fhir_client.search("Schedule", {
            "actor": f"Practitioner/{practitioner_id}"
        })
        
        if not schedule_search or 'entry' not in schedule_search or not schedule_search['entry']:
            logger.info(f"No schedule found for practitioner {practitioner_id}, creating new schedule")
            schedule = create_practitioner_schedule(practitioner_id)
            if not schedule:
                logger.error("Failed to create schedule")
                return []
            schedule_id = schedule['id']
        else:
            schedule_id = schedule_search['entry'][0]['resource']['id']
        
        # Ensure slots exist for the requested date
        create_slots_if_needed(schedule_id, datetime_requested)
        
        # Search for specific slot
        start_time = datetime_requested
        start_range = start_time - timedelta(minutes=30)
        end_range = start_time + timedelta(minutes=30)
        
        slots = fhir_client.search("Slot", {
            "schedule": f"Schedule/{schedule_id}",
            "start": f"ge{start_range.isoformat()}&le{end_range.isoformat()}",
            "status": "free"
        })
        
        if not slots or 'entry' not in slots:
            logger.info(f"No slots found for time {start_time}")
            return []
            
        return slots['entry']

    except Exception as e:
        logger.error(f"Error searching for slots: {str(e)}", exc_info=True)
        return []

def create_slots_if_needed(schedule_id, target_datetime):
    """Create slots for a specific date if they don't exist"""
    try:
        fhir_client = app_config.get_fhir_client()
        
        # Convert to start of day
        start_of_day = target_datetime.replace(hour=9, minute=0, second=0, microsecond=0)
        end_of_day = target_datetime.replace(hour=17, minute=0, second=0, microsecond=0)
        
        # Check if slots already exist
        existing_slots = fhir_client.search("Slot", {
            "schedule": f"Schedule/{schedule_id}",
            "start": f"ge{start_of_day.isoformat()}&le{end_of_day.isoformat()}"
        })
        
        if not existing_slots or 'entry' not in existing_slots or not existing_slots['entry']:
            logger.info(f"Creating slots for {start_of_day.date()}")
            current_time = start_of_day
            
            while current_time < end_of_day:
                slot = {
                    "resourceType": "Slot",
                    "schedule": {"reference": f"Schedule/{schedule_id}"},
                    "status": "free",
                    "start": current_time.isoformat(),
                    "end": (current_time + timedelta(minutes=30)).isoformat()
                }
                
                try:
                    fhir_client.create("Slot", slot)
                    logger.debug(f"Created slot for {current_time.isoformat()}")
                except Exception as e:
                    logger.error(f"Failed to create slot for {current_time.isoformat()}: {str(e)}")
                
                current_time += timedelta(minutes=30)
            
            return True
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating slots: {str(e)}", exc_info=True)
        return False
    

schedule_manager = ScheduleManager(fhir_client, logger)
def get_appointment_schedule(practitioner_id):
    """Retrieve the appointment schedule for a practitioner."""
    return fhir_client.search("Schedule", {"actor": f"Practitioner/{practitioner_id}"})


def create_practitioner_schedule(practitioner_id):
    """Creates a new schedule for a practitioner"""
    try:
        fhir_client = app_config.get_fhir_client()
        
        schedule = {
            "resourceType": "Schedule",
            "active": True,
            "serviceCategory": [{"text": "Consultation"}],
            "serviceType": [{"text": "Primary Care Physician"}],
            "actor": [{
                "reference": f"Practitioner/{practitioner_id}",
                "type": "Practitioner"
            }],
            "planningHorizon": {
                "start": datetime.now(ZoneInfo("UTC")).isoformat(),
                "end": (datetime.now(ZoneInfo("UTC")) + timedelta(days=90)).isoformat()
            }
        }
        
        return fhir_client.create("Schedule", schedule)
        
    except Exception as e:
        logger.error(f"Error creating schedule: {str(e)}", exc_info=True)
        return None

def create_slots_for_date(schedule_id, date):
    """
    Creates slots for a specific date only.
    """
    try:
        # Convert to clinic timezone if not already
        clinic_tz = ZoneInfo("America/New_York")
        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace('Z', '+00:00'))
        date = date.astimezone(clinic_tz)
        
        # Start and end times in clinic timezone
        current = datetime.combine(date.date(), time(9, 0), tzinfo=clinic_tz)
        end_time = datetime.combine(date.date(), time(17, 0), tzinfo=clinic_tz)
        
        created_slots = []
        while current < end_time:
            if current.weekday() < 5:  # Weekdays only
                slot = {
                    "resourceType": "Slot",
                    "schedule": {"reference": f"Schedule/{schedule_id}"},
                    "status": "free",
                    "start": current.isoformat(),
                    "end": (current + timedelta(minutes=30)).isoformat()
                }
                created = fhir_client.create("Slot", slot)
                if created:
                    created_slots.append(created)
            current += timedelta(minutes=30)
            
        logger.info(f"Created {len(created_slots)} slots for date {date.date()}")
        return True
    except Exception as e:
        logger.error(f"Error creating slots: {e}", exc_info=True)
        return False
    
def ensure_extended_schedule(practitioner_id, requested_date):
    """
    Ensures schedule exists and has slots for the requested date.
    Creates schedule and slots if needed.
    """
    try:
        schedule_manager = ScheduleManager(app_config.get_fhir_client(), logger)
        
        # Search for existing schedule
        schedule_results = schedule_manager.fhir_client.search("Schedule", {
            "actor": f"Practitioner/{practitioner_id}"
        })
        
        if not schedule_results or 'entry' not in schedule_results:
            # Create new schedule
            schedule = schedule_manager.create_unlimited_schedule(practitioner_id)
            if not schedule:
                logger.error("Failed to create schedule")
                return False
            schedule_id = schedule['id']
        else:
            schedule_id = schedule_results['entry'][0]['resource']['id']
        
        # Create slots for the date if they don't exist
        start_of_day = requested_date.replace(hour=9, minute=0, second=0, microsecond=0)
        slots = schedule_manager.fhir_client.search("Slot", {
            "schedule": f"Schedule/{schedule_id}",
            "start": f"ge{start_of_day.isoformat()}"
        })
        
        if not slots or 'entry' not in slots:
            return create_slots_for_date(schedule_id, requested_date)
            
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring schedule: {str(e)}", exc_info=True)
        return False
def find_next_available_slots(practitioner_id, from_datetime, limit=5):
    """
    Finds the next available slots, checking for existing appointments.
    """
    try:
        logger.debug(f"Finding next available slots for practitioner {practitioner_id} from {from_datetime}")
        
        # Convert input datetime
        from_dt = datetime.fromisoformat(from_datetime.replace('Z', '+00:00'))
        end_dt = from_dt + timedelta(days=30)  # Look ahead 30 days
        
        # Get all existing appointments within the date range
        appointment_params = {
            'practitioner': f"Practitioner/{practitioner_id}",
            'date': f"ge{from_dt.isoformat()}&le{end_dt.isoformat()}",
            'status': 'booked,pending'
        }
        existing_appointments = fhir_client.search('Appointment', appointment_params)
        booked_times = set()
        
        if existing_appointments and 'entry' in existing_appointments:
            for appt in existing_appointments['entry']:
                start_time = appt['resource'].get('start')
                if start_time:
                    booked_times.add(start_time)
        
        available_slots = []
        current = from_dt
        
        while current <= end_dt and len(available_slots) < limit:
            # Skip weekends
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
                
            # Check each time slot during business hours
            day_start = current.replace(hour=9, minute=0, second=0, microsecond=0)
            day_end = current.replace(hour=17, minute=0, second=0, microsecond=0)
            
            slot_time = day_start
            while slot_time < day_end:
                # Skip if slot is already booked
                if slot_time.isoformat() not in booked_times:
                    available_slots.append(slot_time.strftime("%A, %B %d, %Y at %I:%M %p"))
                    if len(available_slots) >= limit:
                        break
                slot_time += timedelta(minutes=30)
                
            current += timedelta(days=1)
        
        return available_slots
        
    except Exception as e:
        logger.error(f"Error in find_next_available_slots: {str(e)}")
        return []
    
def get_patient_appointments(patient_id):
    """Get all upcoming appointments for a patient"""
    try:
        fhir_client = app_config.get_fhir_client()
        current_time = datetime.now(ZoneInfo("UTC")).isoformat()
        
        response = fhir_client.search("Appointment", {
            "patient": f"Patient/{patient_id}",
            "date": f"ge{current_time}",
            "_sort": "date",
            "_count": 10
        })
        
        if not response or 'entry' not in response:
            return []
            
        return response['entry']
        
    except Exception as e:
        logger.error(f"Error getting patient appointments: {str(e)}", exc_info=True)
        return []
    
@shared_task
def process_medication_reminders():
    """Process all due medication reminders."""
    reminder_service = MedicationAdherenceReminderService()
    current_time = get_current_time()
    
    try:
        due_reminders = reminder_service.get_due_reminders(current_time)
        
        for reminder in due_reminders:
            try:
                send_reminder(reminder)
            except Exception as e:
                logger.error(f"Failed to send reminder for patient {reminder['patient_id']}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Failed to process medication reminders: {str(e)}")
        raise

async def send_reminder(reminder):
    """Send individual reminder message."""
    from ..handlers.chat_handler import ChatHandler
    
    chat_handler = ChatHandler(session_data={}, user_message="", user_id=None)
    message = f"Time to take your {reminder['medication_name']}. Reply 'TAKEN' when done."
    
    await chat_handler.send_message(
        to_number=reminder["phone_number"], 
        message=message
    )

# Add to your CELERYBEAT_SCHEDULE in settings or scheduler config
CELERYBEAT_SCHEDULE = {
    # ... your existing scheduled tasks ...
    'morning-medication-reminders': {
        'task': 'views.services.scheduler.process_medication_reminders',
        'schedule': crontab(hour=9, minute=0)
    },
    'afternoon-medication-reminders': {
        'task': 'views.services.scheduler.process_medication_reminders',
        'schedule': crontab(hour=14, minute=0)
    },
    'evening-medication-reminders': {
        'task': 'views.services.scheduler.process_medication_reminders',
        'schedule': crontab(hour=20, minute=0)
    }
}
print ("37")