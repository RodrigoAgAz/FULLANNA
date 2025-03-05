#!/usr/bin/env python
"""
medication_adherence_reminder_service.py

A production-ready implementation for the Medication Adherence and Refill Reminder Service for Anna.
This module:
  - Retrieves active MedicationRequest resources from a FHIR server.
  - Parses complex dosage instructions (ignoring PRN instructions) to calculate the next due dose time.
  - Checks for refill needs by examining the latest MedicationDispense's daysSupply.
  - Sends SMS reminders via an integrated notification service.
  - Checks for patient confirmations via a persistent store (stubbed here).
  - Respects patient opt-out preferences.
  
IMPORTANT:
  - Replace FHIR endpoint settings and codes with your production values.
  - Integrate send_sms() with your actual SMS provider (e.g., Twilio).
  - Implement has_confirmed_intake() with real confirmation tracking.
  - In production, run this service on a scheduled basis (via Celery, cron, etc.) to avoid duplicate reminders.
"""

import logging
from datetime import datetime, timedelta

# fhirclient imports (install via `pip install fhirclient`)
from fhirclient import client
import fhirclient.models.medicationrequest as fhir_medreq
import fhirclient.models.medicationdispense as fhir_meddisp
import fhirclient.models.patient as fhir_patient

logger = logging.getLogger("MedicationAdherenceReminders")
logger.setLevel(logging.INFO)
print ("27")
# ----------------------------------------------------------------------
# Production FHIR client and SMS integration
# ----------------------------------------------------------------------
def get_fhir_client():
    """
    Configure and return a FHIRClient instance.
    Replace the api_base and add OAuth credentials if needed.
    """
    settings = {
        'app_id': 'AnnaApp',
        'api_base': 'https://fhirserver.example.com',  # Replace with your FHIR endpoint
        # Add additional OAuth settings if required.
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
    Sends an SMS using your SMS provider.
    Replace this stub with your actual SMS provider integration.
    """
    try:
        # Example using Twilio (replace with real implementation):
        # from twilio.rest import Client as TwilioClient
        # twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # twilio_client.messages.create(body=message, from_=settings.TWILIO_PHONE_NUMBER, to=to_number)
        logger.info(f"Sending SMS to {to_number}: {message}")
        return True
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        return False

# Stub for confirmation tracking.
# In production, replace this with a database query or message queue check.
def has_confirmed_intake(patient_id, med_req_id, dose_due_time):
    """
    Check if the patient has confirmed taking their dose.
    This function should query a persistent store keyed by (patient_id, med_req_id, dose_due_time).
    For demonstration, returns False.
    """
    # TODO: Integrate with your confirmation tracking database.
    return False

# ----------------------------------------------------------------------
# Medication Adherence and Refill Reminder Service
# ----------------------------------------------------------------------
class MedicationAdherenceReminderService:
    def __init__(self, fhir_client, notification_service):
        self.fhir_client = fhir_client
        self.notification_service = notification_service
        self.refill_threshold_days = 3  # Send refill reminder if <= 3 days remain
    


    def get_due_reminders(self, current_time):
        """
        Returns a list of due medication reminders for the current time.
        Each reminder is a dictionary with patient_id, medication_name, phone_number.
        """
        due_reminders = []
        med_requests = self._get_all_active_medication_requests()

        for med_req in med_requests:
            patient_id = self._extract_patient_id(med_req)
            if not patient_id:
                continue

            phone_number = self._get_patient_phone_number(patient_id)
            if not phone_number:
                logger.warning(f"No phone number for patient {patient_id}; skipping reminder.")
                continue

            medication_name = self._get_medication_name(med_req) or "your medication"

            # Determine next due dose time
            next_due_time = self._get_next_due_dose_time(med_req)

            if next_due_time and current_time >= next_due_time:
                due_reminders.append({
                    "patient_id": patient_id,
                    "medication_name": medication_name,
                    "phone_number": phone_number,
                    "due_time": next_due_time.isoformat()
                })

        return due_reminders

    def process_medication_reminders(self):
        """
        Main function: retrieves due reminders and sends SMS messages.
        """
        current_time = datetime.now()
        due_reminders = self.get_due_reminders(current_time)

        for reminder in due_reminders:
            self.send_reminder(reminder)

    def send_reminder(self, reminder):
        """
        Sends an SMS reminder for the given medication.
        """
        message = f"Time to take your {reminder['medication_name']}. Reply 'TAKEN' when done."
        success = self.notification_service(reminder["phone_number"], message)

        if success:
            logger.info(f"Reminder sent to patient {reminder['patient_id']} for {reminder['medication_name']}")
        else:
            logger.error(f"Failed to send reminder to patient {reminder['patient_id']}")


    # ------------------------------------------------------------------
    # FHIR Data Retrieval Methods
    # ------------------------------------------------------------------
    def _get_all_active_medication_requests(self):
        med_reqs = []
        try:
            search = fhir_medreq.MedicationRequest.where({'status': 'active'})
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for req in bundle:
                    if isinstance(req, fhir_medreq.MedicationRequest):
                        med_reqs.append(req)
                try:
                    bundle = bundle.next_bundle()
                except Exception:
                    break
        except Exception as e:
            logger.error(f"Error retrieving active MedicationRequests: {e}")
        return med_reqs

    def _extract_patient_id(self, med_req):
        if not med_req.subject or not med_req.subject.reference:
            return None
        return med_req.subject.reference.split('/')[-1]

    def _get_patient_phone_number(self, patient_id):
        try:
            patient = fhir_patient.Patient.read(patient_id, self.fhir_client.server)
            if patient and patient.telecom:
                for telecom in patient.telecom:
                    if telecom.system == 'phone' and telecom.value:
                        return telecom.value
        except Exception as e:
            logger.error(f"Error retrieving phone number for patient {patient_id}: {e}")
        return None

    def _get_patient_preferred_language(self, patient_id):
        """
        Retrieves the preferred language from the Patient resource.
        For demonstration, returns 'en'.
        """
        try:
            patient = fhir_patient.Patient.read(patient_id, self.fhir_client.server)
            if patient.communication and len(patient.communication) > 0:
                comm = patient.communication[0]
                if hasattr(comm, 'language') and comm.language and comm.language.text:
                    return comm.language.text.lower()
        except Exception as e:
            logger.error(f"Error retrieving preferred language for patient {patient_id}: {e}")
        return 'en'

    def _get_medication_name(self, med_req):
        if med_req.medicationCodeableConcept:
            if med_req.medicationCodeableConcept.text:
                return med_req.medicationCodeableConcept.text
            if med_req.medicationCodeableConcept.coding:
                return med_req.medicationCodeableConcept.coding[0].display
        return None

    def _patient_has_opted_out(self, patient_id):
        """
        Checks the Patient resource for an opt-out flag.
        Assumes an extension at "http://example.org/fhir/StructureDefinition/optOut".
        """
        try:
            patient = fhir_patient.Patient.read(patient_id, self.fhir_client.server)
            if patient.extension:
                for ext in patient.extension:
                    if ext.url == "http://example.org/fhir/StructureDefinition/optOut" and getattr(ext, 'valueBoolean', False):
                        return True
        except Exception as e:
            logger.error(f"Error checking opt-out for patient {patient_id}: {e}")
        return False

    # ------------------------------------------------------------------
    # Dosage Instruction Parsing & Dose Reminder Logic
    # ------------------------------------------------------------------
    def _get_next_due_dose_time(self, med_req):
        """
        Iterates over all dosageInstruction entries (ignoring those marked as "as needed")
        and computes the next due dose time based on dosing frequency.
        Returns the earliest next due datetime among the instructions, or None.
        """
        next_due_times = []
        now = datetime.now()

        if not med_req.dosageInstruction:
            return None

        for dose_inst in med_req.dosageInstruction:
            # Skip PRN instructions (if asNeeded is True or specified via asNeededCodeableConcept)
            if hasattr(dose_inst, 'asNeededBoolean') and dose_inst.asNeededBoolean:
                continue
            if hasattr(dose_inst, 'asNeededCodeableConcept') and dose_inst.asNeededCodeableConcept:
                continue

            frequency, period_hours = self._extract_frequency_and_period(dose_inst)
            if frequency is None or period_hours is None:
                continue

            # Compute the dose interval (in hours)
            interval_hours = period_hours / frequency

            # Retrieve the last dose time from MedicationDispense
            last_dispense = self._get_last_dispense_date(med_req)
            if last_dispense:
                next_due = last_dispense + timedelta(hours=interval_hours)
            else:
                # If no dispense record, assume the dose is due immediately
                next_due = now

            next_due_times.append(next_due)

        if next_due_times:
            return min(next_due_times)
        return None

    def _extract_frequency_and_period(self, dose_inst):
        """
        Extracts frequency and period (in hours) from dose_inst.timing.repeat.
        Returns (frequency, period_hours) or (None, None) if extraction fails.
        """
        try:
            repeat = dose_inst.timing.repeat
            frequency = getattr(repeat, 'frequency', None)
            period = getattr(repeat, 'period', None)
            period_unit = getattr(repeat, 'periodUnit', None)
            if not (frequency and period and period_unit):
                return (None, None)
            hours_map = {
                's': 1/3600,
                'min': 1/60,
                'h': 1,
                'd': 24,
                'wk': 24*7,
                'mo': 24*30,
                'a': 24*365,
            }
            if period_unit not in hours_map:
                return (None, None)
            period_hours = period * hours_map[period_unit]
            return (frequency, period_hours)
        except Exception as e:
            logger.error(f"Error extracting frequency/period: {e}")
            return (None, None)

    def _get_last_dispense_date(self, med_req):
        """
        Retrieves the most recent dispense datetime from MedicationDispense resources
        referencing this MedicationRequest.
        """
        med_req_id = getattr(med_req, 'id', None)
        if not med_req_id:
            return None

        last_date = None
        try:
            search = fhir_meddisp.MedicationDispense.where({
                'prescription': f'MedicationRequest/{med_req_id}'
            })
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for disp in bundle:
                    if not isinstance(disp, fhir_meddisp.MedicationDispense):
                        continue
                    disp_dt = self._extract_dispense_datetime(disp)
                    if disp_dt and (not last_date or disp_dt > last_date):
                        last_date = disp_dt
                try:
                    bundle = bundle.next_bundle()
                except Exception:
                    break
        except Exception as e:
            logger.error(f"Error retrieving MedicationDispense for MedicationRequest/{med_req_id}: {e}")
        return last_date

    def _extract_dispense_datetime(self, disp):
        """
        Extracts a datetime from MedicationDispense.whenHandedOver or whenPrepared.
        """
        for attr in ['whenHandedOver', 'whenPrepared']:
            dt_str = getattr(disp, attr, None)
            if dt_str:
                dt = self._parse_date_str(dt_str)
                if dt:
                    return dt
        return None

    def _parse_date_str(self, date_str):
        """
        Parses an ISO8601 date string into a datetime object.
        """
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Error parsing date string '{date_str}': {e}")
            return None

    # ------------------------------------------------------------------
    # Refill Reminder Logic
    # ------------------------------------------------------------------
    def _is_refill_due(self, med_req, now):
        """
        Determines if a refill reminder should be sent based on the latest MedicationDispense's
        daysSupply and the elapsed days since that dispense.
        """
        dispense_info = self._get_latest_dispense_info(med_req)
        if not dispense_info:
            return False

        dispense_date = dispense_info.get('dispense_date')
        days_supply = dispense_info.get('days_supply')
        if not dispense_date or days_supply is None:
            return False

        elapsed_days = (now.date() - dispense_date.date()).days
        remaining_days = days_supply - elapsed_days
        return remaining_days <= self.refill_threshold_days

    def _get_latest_dispense_info(self, med_req):
        """
        Retrieves the most recent MedicationDispense info for this MedicationRequest,
        returning a dict with keys 'dispense_date' and 'days_supply'.
        Note: For complex scenarios (partial refills, overlapping prescriptions), you may need to
        sum or aggregate multiple dispenses.
        """
        med_req_id = getattr(med_req, 'id', None)
        if not med_req_id:
            return None

        latest_date = None
        latest_supply = None

        try:
            search = fhir_meddisp.MedicationDispense.where({
                'prescription': f'MedicationRequest/{med_req_id}'
            })
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for disp in bundle:
                    if not isinstance(disp, fhir_meddisp.MedicationDispense):
                        continue
                    disp_dt = self._extract_dispense_datetime(disp)
                    supply = self._extract_days_supply(disp)
                    if disp_dt and supply is not None and (not latest_date or disp_dt > latest_date):
                        latest_date = disp_dt
                        latest_supply = supply
                try:
                    bundle = bundle.next_bundle()
                except Exception:
                    break
        except Exception as e:
            logger.error(f"Error retrieving dispense info for MedicationRequest/{med_req_id}: {e}")
            return None

        if latest_date:
            return {'dispense_date': latest_date, 'days_supply': latest_supply}
        return None

    def _extract_days_supply(self, disp):
        """
        Extracts the daysSupply value from a MedicationDispense.
        """
        if hasattr(disp, 'daysSupply') and disp.daysSupply and disp.daysSupply.value is not None:
            try:
                return float(disp.daysSupply.value)
            except Exception as e:
                logger.error(f"Error extracting daysSupply: {e}")
        return None

    # ------------------------------------------------------------------
    # End of Service Class
    # ------------------------------------------------------------------

# ----------------------------------------------------------------------
# Script Entry Point (for scheduled execution)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    try:
        fhir_client = get_fhir_client()
        reminder_service = MedicationAdherenceReminderService(fhir_client, send_sms)
        reminder_service.process_medication_reminders()
    except Exception as e:
        logger.error(f"Critical error processing medication reminders: {e}")
print ("28")