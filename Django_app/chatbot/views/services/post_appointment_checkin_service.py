#!/usr/bin/env python
"""
post_appointment_checkin_service.py

A production-ready example of the Post-Appointment Check-In Service for Anna.
This script retrieves recently completed Appointments from a FHIR server (e.g., those
that ended ~24 hours ago), checks patient details, composes a follow-up SMS message,
and sends the message via an SMS provider (e.g., Twilio). It also contains stubs for
handling patient responses and escalating concerns.

FEATURES:
  1. Appointment Retrieval: Fetches Appointment resources with status='finished' (or 'completed')
     and filters them by end time to approximate a 24-hour post-appointment window.
  2. Patient Data Lookup: Retrieves the Patient resource for each appointment, pulling phone number,
     name, and preferred language.
  3. Personalized Follow-Up Message: Composes a message referencing the patient's appointment details
     and prompts them to respond if they have questions or concerns.
  4. SMS Sending: Integrates with your notification service (send_sms); in production, connect this
     to Twilio or another SMS provider.
  5. Logging & Tracking: Logs all sent messages. Includes a stub for storing these logs in a database
     if desired.
  6. Response Handling: Provides methods for processing inbound patient responses and escalating care
     team follow-up when certain keywords (e.g., "pain", "confused") appear.
  7. Internationalization (Optional): Illustrates a `_translate_message` stub, letting you integrate
     a translation API for patients whose preferred language is not English.

USAGE:
  - Schedule this script (e.g., via Celery or a cron job) to run periodically (daily or hourly),
    ensuring it checks which appointments ended ~24 hours ago.
  - Adjust the follow-up window, codes, and search parameters for your organization's needs.
  - Replace the placeholders in get_fhir_client() and send_sms() with real credentials
    and integration code.
  - Fully implement the response handling in a persistent store or inbound message queue.

IMPORTANT:
  - Thoroughly test in your staging environment before deploying to production.
  - Secure any PHI in logs, databases, and transmissions as required by HIPAA or relevant regulations.
"""

import logging
from datetime import datetime, timedelta

# fhirclient imports (install via `pip install fhirclient`)
from fhirclient import client
import fhirclient.models.appointment as fhir_appointment
import fhirclient.models.patient as fhir_patient

logger = logging.getLogger("PostAppointmentCheckInService")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------------
# Production FHIR client and SMS notification integration
# ---------------------------------------------------------------------------------
print ("31")
def get_fhir_client():
    """
    Configure and return a FHIRClient instance pointed at your FHIR server.
    Update 'api_base' and any OAuth settings as required for production.
    """
    settings = {
        'app_id': 'AnnaApp',
        'api_base': 'https://fhirserver.example.com',  # Replace with your actual endpoint
        # Uncomment/modify if OAuth is required:
        # 'client_id': 'YOUR_CLIENT_ID',
        # 'client_secret': 'YOUR_CLIENT_SECRET',
        # 'authorize_uri': 'https://fhirserver.example.com/auth',
        # 'redirect_uri': 'https://yourapp.example.com/redirect',
    }
    try:
        fhir_client = client.FHIRClient(settings=settings)
        logger.info("FHIR client initialized successfully.")
        return fhir_client
    except Exception as e:
        logger.error(f"Error initializing FHIR client: {e}")
        raise

def send_sms(to_number, message):
    """
    Sends an SMS message via your SMS provider.
    Replace the contents of this function with your actual integration code (e.g., Twilio).
    """
    try:
        logger.info(f"Sending SMS to {to_number}: {message}")
        # Example Twilio usage (pseudo-code):
        # from twilio.rest import Client as TwilioClient
        # import settings  # or use environment variables
        #
        # twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # twilio_client.messages.create(
        #     body=message,
        #     from_=settings.TWILIO_PHONE_NUMBER,
        #     to=to_number
        # )
        return True
    except Exception as e:
        logger.error(f"Error sending SMS to {to_number}: {e}")
        return False

# ---------------------------------------------------------------------------------
# Post-Appointment Check-In Service
# ---------------------------------------------------------------------------------
class PostAppointmentCheckInService:
    def __init__(self, fhir_client, notification_service):
        self.fhir_client = fhir_client
        self.notification_service = notification_service
        
        # How long after an appointment ends before sending a check-in (24h is typical)
        self.followup_delay = timedelta(hours=24)
        # A small tolerance window (in hours) around the exact follow-up time to decide
        # if it's "due now." This helps manage slight scheduling offsets.
        self.followup_tolerance = timedelta(hours=2)

    def process_checkins(self):
        """
        Main entry point:
          1. Retrieves 'finished' Appointments that ended ~24 hours ago.
          2. For each Appointment, fetches the associated Patient, composes an SMS,
             and sends the check-in message.
          3. Logs each successful check-in or any failures.
        """
        now = datetime.now()
        appointments = self._get_appointments_due_for_checkin(now)
        logger.info(f"Found {len(appointments)} appointments due for check-in at {now.isoformat()}")

        for appt in appointments:
            patient_id = self._extract_patient_id_from_appointment(appt)
            if not patient_id:
                logger.warning(f"No patient ID found in Appointment/{appt.id}, skipping check-in.")
                continue

            patient = self._get_patient_resource(patient_id)
            if not patient:
                logger.warning(f"Could not retrieve Patient/{patient_id}, skipping check-in.")
                continue

            phone = self._get_patient_phone_number(patient)
            if not phone:
                logger.warning(f"Patient {patient_id} has no phone number; skipping check-in.")
                continue

            patient_name = self._get_patient_name(patient)
            preferred_lang = self._get_patient_preferred_language(patient)

            message = self._compose_checkin_message(appt, patient_name)
            message = self._translate_message(message, preferred_lang)

            # Send the SMS check-in
            if self.notification_service(phone, message):
                logger.info(
                    f"Sent post-appointment check-in to patient {patient_id} for Appointment/{appt.id}"
                )
                self._log_checkin_sent(patient_id, appt.id, message)
            else:
                logger.error(f"Failed to send post-appointment check-in for Patient/{patient_id}")

    # ------------------------------------------------------------------
    # Appointment Retrieval & Filtering
    # ------------------------------------------------------------------
    def _get_appointments_due_for_checkin(self, now):
        """
        Retrieves Appointment resources whose status is 'finished' (or 'completed'),
        and whose 'end' time is about 'followup_delay' hours ago, within a tolerance window.
        
        For example, if followup_delay = 24h, we look for appointments that ended between
        (now - 24h - tolerance) and (now - 24h + tolerance).
        """
        # Calculate the time window in which appointments must have ended
        lower_bound = (now - self.followup_delay - self.followup_tolerance)
        upper_bound = (now - self.followup_delay + self.followup_tolerance)

        # We'll build a date filter that your FHIR server might accept. For instance,
        # some servers allow searching by 'date=lt' or 'end=lt'. Check your FHIR server's
        # documentation. Here we assume 'date' can refer to Appointment.start or end time,
        # or we might try a custom param:
        #
        #   'date=ge{lower_bound.isoformat()},le{upper_bound.isoformat()}'
        # 
        # but many servers differ. We'll keep it simple, then manually filter below.
        appointments = []
        try:
            search = fhir_appointment.Appointment.where({'status': 'finished'})
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for appt in bundle:
                    if not isinstance(appt, fhir_appointment.Appointment):
                        continue
                    end_time = self._get_appointment_end_time(appt)
                    if end_time and lower_bound <= end_time <= upper_bound:
                        appointments.append(appt)

                try:
                    bundle = bundle.next_bundle()
                except Exception:
                    break
        except Exception as e:
            logger.error(f"Error retrieving finished Appointments from FHIR: {e}")

        return appointments

    def _get_appointment_end_time(self, appt):
        """
        Extracts the 'end' time from the Appointment resource. 
        Appointment.end is an ISO8601 string. e.g. '2023-07-05T14:30:00Z'.
        """
        if hasattr(appt, 'end') and appt.end:
            try:
                return datetime.fromisoformat(appt.end.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Error parsing appointment end time for Appointment/{appt.id}: {e}")
        return None

    # ------------------------------------------------------------------
    # Patient Data Retrieval
    # ------------------------------------------------------------------
    def _extract_patient_id_from_appointment(self, appt):
        """
        Extracts the Patient ID from Appointment.subject.reference (e.g. 'Patient/123').
        """
        if not appt.subject or not appt.subject.reference:
            return None
        parts = appt.subject.reference.split('/')
        return parts[-1] if len(parts) > 1 else None

    def _get_patient_resource(self, patient_id):
        """
        Retrieves a FHIR Patient resource by ID.
        """
        try:
            return fhir_patient.Patient.read(patient_id, self.fhir_client.server)
        except Exception as e:
            logger.error(f"Error retrieving Patient/{patient_id}: {e}")
            return None

    def _get_patient_phone_number(self, patient):
        """
        Searches Patient.telecom for a phone number to send SMS messages.
        """
        if patient.telecom:
            for telecom in patient.telecom:
                if telecom.system == 'phone' and telecom.value:
                    return telecom.value
        return None

    def _get_patient_name(self, patient):
        """
        Returns a readable patient name from patient.name.
        """
        if patient.name and len(patient.name) > 0:
            name = patient.name[0]
            given = " ".join(name.given) if name.given else ""
            family = name.family if name.family else ""
            full_name = f"{given} {family}".strip()
            return full_name if full_name else "Patient"
        return "Patient"

    def _get_patient_preferred_language(self, patient):
        """
        Tries to retrieve the patient's preferred language code from patient.communication.
        Returns 'en' if not found.
        """
        if patient.communication and len(patient.communication) > 0:
            comm = patient.communication[0]
            if hasattr(comm, 'language') and comm.language and comm.language.text:
                return comm.language.text.lower()  # e.g. 'en', 'es', etc.
        return 'en'

    # ------------------------------------------------------------------
    # Composing & Translating the Check-In Message
    # ------------------------------------------------------------------
    def _compose_checkin_message(self, appt, patient_name):
        """
        Builds a personalized message for the patient referencing their appointment.
        You can extract appointment date/time, provider name, or other relevant details.
        """
        provider_name = self._get_appointment_provider(appt) or "your provider"
        appt_start_str = self._format_appointment_time(appt)
        message = (
            f"Hello {patient_name},\n\n"
            f"We hope your appointment with {provider_name} on {appt_start_str} went well. "
            "Please reply with any questions you have or type 'OK' if everything is clear. "
            "If you are experiencing any issues (e.g., pain, confusion about instructions), reply 'HELP'."
        )
        return message

    def _get_appointment_provider(self, appt):
        """
        Example method to extract the provider's name (or org name) from the Appointment participants.
        In real usage, you'd look for the participant with role='primary performer' or similar,
        then read their display name or reference (e.g., Practitioner/123).
        """
        if not appt.participant:
            return None
        for participant in appt.participant:
            # Check if participant is a Practitioner or Organization with a display
            if participant.actor and participant.actor.display:
                return participant.actor.display
        return None

    def _format_appointment_time(self, appt):
        """
        Formats the appointment start time as a human-readable string.
        """
        if hasattr(appt, 'start') and appt.start:
            try:
                start_dt = datetime.fromisoformat(appt.start.replace('Z', '+00:00'))
                # Format as, e.g., 'July 5 at 2:30 PM'
                return start_dt.strftime("%B %d at %I:%M %p")
            except Exception as e:
                logger.warning(f"Error parsing appointment start time for Appointment/{appt.id}: {e}")
        return "your recent appointment"

    def _translate_message(self, message, target_language):
        """
        Stub for translating a message into another language.
        Integrate a real translation API (e.g., Google Cloud Translate) in production.
        """
        if target_language.lower() == 'en':
            return message
        # Example: prefix with language code for demonstration
        # In production, call your actual translation service here
        return f"[{target_language.upper()} Translation Placeholder] {message}"

    # ------------------------------------------------------------------
    # Logging & Response Handling
    # ------------------------------------------------------------------
    def _log_checkin_sent(self, patient_id, appointment_id, message):
        """
        Logs that we sent a check-in. In production, consider storing in a database
        for historical tracking.
        """
        logger.info(
            f"Check-in message recorded for Patient/{patient_id} Appointment/{appointment_id}: {message}"
        )

    def process_response(self, patient_id, appointment_id, response_text):
        """
        Example method to handle inbound responses from patients.
        In production, you'd call this from an SMS webhook or a queue.
        Checks for concerning keywords to decide if escalation is necessary.
        """
        self._log_patient_response(patient_id, appointment_id, response_text)
        if self._detect_concerning_keywords(response_text):
            self._escalate_issue(patient_id, appointment_id, response_text)

    def _log_patient_response(self, patient_id, appointment_id, response_text):
        """
        Logs the patient response. Again, store in a database if you want
        persistent records of inbound messages.
        """
        logger.info(
            f"Received response from Patient/{patient_id} Appointment/{appointment_id}: {response_text}"
        )

    def _detect_concerning_keywords(self, response_text):
        """
        Very simple check for words that indicate patient distress or confusion.
        Expand with your own synonyms or logic as needed.
        """
        keywords = ['confused', 'side effect', 'pain', 'problem', 'worry', 'help']
        lower_text = response_text.lower()
        return any(keyword in lower_text for keyword in keywords)

    def _escalate_issue(self, patient_id, appointment_id, response_text):
        """
        Example of escalating a concerning response. In production, you might:
          - Notify a care coordinator via email or SMS
          - Generate a task in your EHR or ticket system
          - Prompt a telehealth nurse to call the patient
        """
        logger.warning(
            f"Escalation triggered for Patient/{patient_id} Appointment/{appointment_id}: {response_text}"
        )
        # Implement your actual escalation workflow (alerts, tasks, etc.)

# ---------------------------------------------------------------------------------
# Script Entry Point (Scheduling / Cron / Celery)
# ---------------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    try:
        fhir_client = get_fhir_client()
        checkin_service = PostAppointmentCheckInService(fhir_client, send_sms)
        checkin_service.process_checkins()
    except Exception as e:
        logger.error(f"Critical error in processing post-appointment check-ins: {e}")
print ("32")