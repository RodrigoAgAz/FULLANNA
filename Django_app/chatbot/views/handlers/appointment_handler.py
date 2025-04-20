# chatbot/views/handlers/appointment_handler.py

from datetime import datetime
from zoneinfo import ZoneInfo
from django.conf import settings
from chatbot.views.utils.formatters import get_resource_name
from chatbot.views.utils.datetime_utils import format_datetime_for_user
from chatbot.views.config import config as app_config  # Fixed import
from ..services.session import update_session
from ..services.fhir_service import get_user_appointments, get_practitioner
import logging

logger = logging.getLogger('chatbot')
logger.debug("Appointment handler module loaded")
def handle_appointment_query(session, user_message):
    """Handle showing upcoming appointments"""
    try:
        if not session.get('patient'):
            return "Please verify your identity first."
        
        patient_id = session['patient']['id']
        logger.info(f"Fetching appointments for patient {patient_id}")
        
        # Get FHIR client from app_config
        fhir_client = app_config.get_fhir_client()  # Using the correct config
        
        # Build the search parameters
        current_time = datetime.now(ZoneInfo(settings.TIME_ZONE)).isoformat()
        search_params = {
            "patient": f"Patient/{patient_id}",
            "date": f"ge{current_time}",
            "_sort": "date"
        }
        
        # Search for appointments
        logger.debug(f"Searching appointments with params: {search_params}")
        response = fhir_client.search("Appointment", search_params)
        
        if not response or 'entry' not in response or not response['entry']:
            return "You don't have any upcoming appointments scheduled."
        
        # Format appointments
        appointments = []
        for entry in response.get('entry', []):
            appt = entry['resource']
            
            # Skip non-booked appointments
            if appt.get('status') not in ['booked', 'pending']:
                continue
            
            # Get the appointment time
            start_time = datetime.fromisoformat(appt['start'].replace('Z', '+00:00'))
            local_time = start_time.astimezone(ZoneInfo(settings.TIME_ZONE))
            formatted_time = local_time.strftime("%A, %B %d, %Y at %I:%M %p %Z")
            
            # Get practitioner info
            practitioner_name = "Unknown Provider"
            for participant in appt.get('participant', []):
                if participant.get('actor', {}).get('type') == 'Practitioner':
                    pract_ref = participant['actor']['reference']
                    try:
                        pract_id = pract_ref.split('/')[-1]
                        practitioner = fhir_client.read("Practitioner", pract_id)
                        if practitioner and 'name' in practitioner:
                            name_data = practitioner['name'][0] if isinstance(practitioner['name'], list) else practitioner['name']
                            if isinstance(name_data, dict):
                                if 'text' in name_data:
                                    practitioner_name = f"Dr. {name_data['text']}"
                                elif 'family' in name_data:
                                    given = name_data.get('given', [''])[0]
                                    practitioner_name = f"Dr. {given} {name_data['family']}"
                    except Exception as e:
                        logger.error(f"Error getting practitioner details: {str(e)}")
                    break
            
            appointments.append(f"- {formatted_time} with {practitioner_name}")
            if appt.get('description'):
                appointments[-1] += f" ({appt['description']})"
        
        if not appointments:
            return "You don't have any upcoming appointments scheduled."
        
        return "Here are your upcoming appointments:\n\n" + "\n".join(appointments)
        
    except Exception as e:
        logger.error(f"Error handling appointment query: {str(e)}", exc_info=True)
        return "I'm sorry, I couldn't retrieve your appointments at this time. Please try again later."

async def handle_appointment_cancellation(session, user_message):
    """Handle appointment cancellation requests"""
    try:
        # Get FHIR client from app_config
        fhir_client = app_config.get_fhir_client()

        if not session.get('patient'):
            return "Please verify your identity first."
            
        patient_id = session['patient']['id']
        logger.debug(f"Handling appointment cancellation for patient {patient_id}")
        
        # If we're already in cancellation mode
        if session.get('cancellation_options'):
            if user_message.isdigit():
                option_num = user_message
                if option_num in session['cancellation_options']:
                    appt_id = session['cancellation_options'][option_num]
                    try:
                        appointment = fhir_client.read("Appointment", appt_id)
                        if appointment:
                            appointment['status'] = 'cancelled'
                            fhir_client.update("Appointment", appt_id, appointment)
                            session.pop('cancellation_options', None)
                            # Use the user_id (from phone) rather than relying on session['id'] which may not exist
                            user_id = session.get('phone_number') or session.get('user_id')
                            await update_session(user_id, session)
                            
                            # Audit the cancellation
                            from audit.utils import log_event
                            log_event(
                                actor=user_id,
                                action="appointment.cancelled",
                                resource=f"Appointment/{appt_id}",
                                meta={
                                    "patient_id": patient_id,
                                    "appointment_status": "cancelled"
                                }
                            )
                            
                            return "Your appointment has been cancelled. Is there anything else I can help you with?"
                    except Exception as e:
                        logger.error(f"Error cancelling appointment {appt_id}: {str(e)}")
                        return "There was an error cancelling your appointment. Please try again."
                return "Please select a valid appointment number from the list."
        
        # Get upcoming appointments
        current_time = datetime.now(ZoneInfo(settings.TIME_ZONE)).isoformat()
        search_params = {
            "patient": f"Patient/{patient_id}",
            "date": f"ge{current_time}",
            "status": "booked,pending",
            "_sort": "date"
        }
        
        appointments = fhir_client.search("Appointment", search_params)
        if not appointments or 'entry' not in appointments or not appointments['entry']:
            return "You don't have any upcoming appointments to cancel."
            
        # Create numbered list of appointments
        options = {}
        messages = ["Which appointment would you like to cancel?"]
        
        for i, entry in enumerate(appointments['entry'], 1):
            appt = entry['resource']
            start_time = datetime.fromisoformat(appt['start'].replace('Z', '+00:00'))
            local_time = start_time.astimezone(ZoneInfo(settings.TIME_ZONE))
            formatted_time = local_time.strftime("%A, %B %d at %I:%M %p")
            
            # Get practitioner info
            practitioner_name = "Unknown Provider"
            for participant in appt.get('participant', []):
                if participant.get('actor', {}).get('type') == 'Practitioner':
                    pract_ref = participant['actor']['reference']
                    try:
                        pract = fhir_client.read("Practitioner", pract_ref.split('/')[-1])
                        if pract:
                            practitioner_name = f"Dr. {get_resource_name(pract)}"
                    except Exception as e:
                        logger.error(f"Error getting practitioner: {str(e)}")
            
            messages.append(f"{i}. {formatted_time} with {practitioner_name}")
            options[str(i)] = appt['id']
            
        # Store options in session
        session['cancellation_options'] = options
        # Use the user_id (from phone) rather than relying on session['id'] which may not exist
        user_id = session.get('phone_number') or session.get('user_id')
        await update_session(user_id, session)
        
        return "\n".join(messages)
        
    except Exception as e:
        logger.error(f"Error handling cancellation: {str(e)}")
        return "I'm sorry, I couldn't process your cancellation request at this time. Please try again later."
logger.debug("Appointment handler module initialization complete")