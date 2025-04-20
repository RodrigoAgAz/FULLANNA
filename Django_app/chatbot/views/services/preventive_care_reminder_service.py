#!/usr/bin/env python
"""
preventive_care_reminder_service.py

A fully implemented example for the Preventive Care Reminder Service in Anna,
using the fhirclient library for querying a FHIR server. This script checks
patients' ages, risk factors (via Condition/Observation), and their latest
screening/Procedure dates to determine if they need various preventive services.
It then sends SMS reminders (via a Twilio-like function).

NOTES:
1. You must install fhirclient (e.g., `pip install fhirclient`) and have a valid
   FHIR endpoint (OAuth or basic auth, as configured in get_fhir_client()).
2. Replace the codes, URLs, and logic to suit your environment. This script
   demonstrates a typical approach but won't work out of the box without
   your actual codes and FHIR server configuration.
3. For real production usage, you may need pagination, concurrency, more refined
   search parameters, and handling of incomplete data or multiple payers.

Preventive Services Covered:
  - Colonoscopy (every 10 years starting at 45)
  - Mammogram (every 18 months starting at 50, or annually if high risk)
  - Diabetes Screening (every 3 years if at risk)
  - Hypertension Check (annually if borderline, every 2 years if normal)
  - Lipid Panel (every 5 years if at risk)
  - Osteoporosis Screening (every 2 years for postmenopausal women)
  - Vision & Hearing Screening (every 2 years)
  - Cervical Cancer Screening (Pap every 3 years from age 21+)
  - Prostate Cancer Screening (not automatically scheduled; discussion-based)
  - Lung Cancer Screening (annual for 55–80 with smoking history)
  - Shingles Vaccine (once at age 50+ if not previously immunized)

If a patient had ANY preventive service in the last 18 months, you may skip sending
some reminders. This logic is handled by `_had_recent_preventive_care()`.

Risk Factor Determination is done by:
  - Checking Conditions or Observations for relevant codes (e.g., obesity, hypertension).
  - Checking the last BP Observation to decide if it’s borderline/elevated.

Robust Error Handling:
  - Each FHIR query is wrapped in try/except blocks to log and handle errors gracefully.
  - If a query fails, we skip that check and continue with other patients.

(c) Example only. Not guaranteed for production.
"""

import logging
from datetime import datetime, timedelta, date

# fhirclient library
from fhirclient import client
import fhirclient.models.patient as fhir_patient
import fhirclient.models.condition as fhir_condition
import fhirclient.models.observation as fhir_observation
import fhirclient.models.procedure as fhir_procedure
import fhirclient.models.immunization as fhir_immunization

# Logging setup
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.debug("Preventive care reminder service module loaded")
# ----------------------------------------------------------------------
# REPLACE THESE WITH REAL CREDENTIALS / ENDPOINTS / OAUTH CONFIG
# ----------------------------------------------------------------------
def get_fhir_client():
    """
    Configure and return a FHIRClient pointed at your FHIR server.
    This example uses a public test server. Replace with your details.
    """
    settings = {
        'app_id': 'AnnaApp',
        'api_base': 'https://server.fire.ly/r4',  # Example test server - change to your endpoint
        # If you have OAuth, you'll need 'authorize_uri', 'redirect_uri', 'client_id', etc.
    }
    return client.FHIRClient(settings=settings)

def send_sms(to_number, message):
    """
    Example of an SMS sending function (Twilio-like).
    Replace with actual integration in production.
    """
    logger.info(f"Sending SMS to {to_number}: {message}")
    # e.g.:
    # twilio_client.messages.create(to=to_number, from_="YourShortCode", body=message)
    return True

# ----------------------------------------------------------------------
# Preventive Care Service Implementation
# ----------------------------------------------------------------------
class PreventiveCareReminderService:
    def __init__(self, fhir_client, notification_service):
        self.fhir_client = fhir_client
        self.notification_service = notification_service

        # Intervals in days
        self.interval_18_months = 18 * 30  # 540 days
        self.colonoscopy_interval = 10 * 365
        self.mammogram_interval = 18 * 30
        self.mammogram_interval_highrisk = 365  # 1 year if high risk
        self.diabetes_interval = 3 * 365
        self.hypertension_interval_normal = 2 * 365
        self.hypertension_interval_elevated = 365
        self.lipid_interval = 5 * 365
        self.osteoporosis_interval = 2 * 365
        self.vision_hearing_interval = 2 * 365
        self.cervical_interval_pap = 3 * 365
        # For co-testing every 5 years, you could define self.cervical_interval_cotesting
        self.lung_interval = 365
        # Prostate screening is discussion-based
        # Shingles vaccine once after 50

    def process_reminders(self):
        """
        Main entry point: gets due reminders and sends them.
        """
        reminders = self.get_due_reminders()
        for reminder in reminders:
            self.send_reminder(reminder)

    def get_due_reminders(self):
        """
        Retrieves all Patients, checks each for needed services, returns a list of reminders.
        """
        reminders = []
        patients = self._get_all_patients()
        now = datetime.now()

        for patient in patients:
            if not patient.id:
                continue

            # Check opt-out
            if self._patient_has_opted_out(patient):
                continue

            phone_number = self._get_patient_phone_number(patient)
            if not phone_number:
                continue

            birth_date = self._get_birth_date(patient)
            if not birth_date:
                continue

            age = self._calculate_age(birth_date, now)

            # We'll collect potential reminders in a local list, then check if we skip some
            patient_reminders = []

            # Check each preventive service
            # 1. Colonoscopy
            if age >= 45:
                if self._needs_colonoscopy(patient.id, now):
                    patient_reminders.append(("Colonoscopy", now.isoformat()))

            # 2. Mammogram for women age >= 50, or high-risk 40+
            if self._is_female(patient):
                if age >= 50:
                    if self._needs_mammogram(patient.id, now, interval=self.mammogram_interval):
                        patient_reminders.append(("Mammogram", now.isoformat()))
                else:
                    # If <50 but high-risk (BRCA, family history, etc.)
                    if age >= 40 and self._is_high_risk_breast_cancer(patient):
                        if self._needs_mammogram(patient.id, now, interval=self.mammogram_interval_highrisk):
                            patient_reminders.append(("Mammogram (High-Risk)", now.isoformat()))

            # 3. Diabetes screening if at risk, every 3 years
            if self._is_at_risk_for_diabetes(patient):
                if self._needs_diabetes_screening(patient.id, now):
                    patient_reminders.append(("Diabetes Screening", now.isoformat()))

            # 4. Hypertension check
            if age >= 18:
                bp_interval = self.hypertension_interval_elevated if self._has_borderline_bp(patient) else self.hypertension_interval_normal
                if self._needs_blood_pressure_check(patient.id, now, bp_interval):
                    patient_reminders.append(("Hypertension Check", now.isoformat()))

            # 5. Lipid panel if at risk
            if self._is_at_risk_for_cardio(patient):
                if self._needs_lipid_panel(patient.id, now):
                    patient_reminders.append(("Cholesterol/Lipid Panel", now.isoformat()))

            # 6. Osteoporosis screening for postmenopausal women
            if self._is_female(patient) and self._is_postmenopausal(age, patient):
                if self._needs_osteoporosis_screening(patient.id, now):
                    patient_reminders.append(("Osteoporosis Screening", now.isoformat()))

            # 7. Vision & Hearing
            if self._needs_vision_hearing_screening(patient.id, now):
                patient_reminders.append(("Vision and Hearing Screening", now.isoformat()))

            # 8. Cervical screening for women 21+
            if self._is_female(patient) and age >= 21:
                if self._needs_cervical_screening(patient.id, now, age):
                    patient_reminders.append(("Cervical Cancer Screening", now.isoformat()))

            # 9. Lung cancer screening for 55–80 with smoking history
            if 55 <= age <= 80 and self._is_eligible_for_lung_screening(patient):
                if self._needs_lung_screening(patient.id, now):
                    patient_reminders.append(("Lung Cancer Screening", now.isoformat()))

            # 10. Shingles vaccine at 50+
            if age >= 50:
                if self._needs_shingles_vaccine(patient.id):
                    patient_reminders.append(("Shingles Vaccine", now.isoformat()))

            # Skip sending if patient had any preventive care in last 18 months
            if patient_reminders and not self._had_recent_preventive_care(patient.id, now, self.interval_18_months):
                for service_name, due_date in patient_reminders:
                    reminders.append({
                        "patient_id": patient.id,
                        "service": service_name,
                        "due_date": due_date,
                        "phone_number": phone_number
                    })

        return reminders

    def send_reminder(self, reminder):
        """
        Sends an SMS reminder for a particular service.
        """
        message = (
            f"Hello! You are due for {reminder['service']}. "
            "Please call or visit us online to schedule your appointment."
        )
        try:
            self.notification_service(reminder['phone_number'], message)
            logger.info(f"Sent {reminder['service']} reminder to patient {reminder['patient_id']}")
        except Exception as e:
            logger.error(f"Error sending reminder to patient {reminder['patient_id']}: {e}")

    # -------------------------------------------------------------
    # PATIENT / DEMOGRAPHIC QUERIES
    # -------------------------------------------------------------
    def _get_all_patients(self):
        """
        Retrieves all Patient records from FHIR. Includes basic
        pagination handling for demonstration. Adjust as needed.
        """
        results = []
        search = fhir_patient.Patient.where({})
        try:
            bundle = search.perform_resources(self.fhir_client.server)
        except Exception as e:
            logger.error(f"Error retrieving Patient resources: {e}")
            return results  # Return empty list on error

        while bundle:
            for resource in bundle:
                if isinstance(resource, fhir_patient.Patient):
                    results.append(resource)
            # Attempt next page
            next_bundle = None
            try:
                next_bundle = bundle.next_bundle()
            except Exception:
                pass
            bundle = next_bundle

        return results

    def _get_patient_phone_number(self, patient):
        """
        Extracts phone number from the Patient.telecom array.
        """
        if not patient.telecom:
            return None
        for telecom in patient.telecom:
            if telecom.system == 'phone' and telecom.value:
                return telecom.value
        return None

    def _get_birth_date(self, patient):
        """
        Returns birth date as a date object, or None.
        """
        if not patient.birthDate:
            return None
        try:
            return datetime.strptime(patient.birthDate, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _calculate_age(self, birth_date, now):
        """
        Returns integer age in years.
        """
        if not birth_date:
            return 0
        return now.year - birth_date.year - ((now.month, now.day) < (birth_date.month, birth_date.day))

    def _patient_has_opted_out(self, patient):
        """
        Example: checks a custom extension for an opt-out flag.
        Replace with how your system stores opt-out data.
        """
        # Suppose there's an extension with url "http://example.org/fhir/StructureDefinition/optOut"
        if not patient.extension:
            return False
        for ext in patient.extension:
            if ext.url == "http://example.org/fhir/StructureDefinition/optOut":
                if hasattr(ext, 'valueBoolean') and ext.valueBoolean is True:
                    return True
        return False

    def _is_female(self, patient):
        return (patient.gender or "").lower() == "female"

    def _is_postmenopausal(self, age, patient):
        """
        A simplistic assumption: age >= 50 -> postmenopausal.
        Replace with logic for actual Observations or Conditions.
        """
        return age >= 50

    # -------------------------------------------------------------
    # RISK FACTOR CHECKS: Real FHIR Queries for Conditions/Obs
    # -------------------------------------------------------------
    def _is_high_risk_breast_cancer(self, patient):
        """
        Example: checks for Conditions indicating a BRCA mutation or strong family history.
        (Using hypothetical SNOMED/ICD codes.)
        """
        high_risk_codes = [
            "195967001",  # SNOMED for BRCA1 mutation
            "254632001",  # Family history of breast cancer
        ]
        return self._has_any_condition(patient.id, high_risk_codes)

    def _is_at_risk_for_diabetes(self, patient):
        """
        Checks if patient has diabetes or is obese (BMI >30), or has a condition indicating
        prediabetes/family history.
        """
        # Condition codes for diabetes/prediabetes
        diabetes_codes = [
            "44054006",   # Diabetes mellitus type 2
            "15777000",   # Diabetes mellitus type 1
            "42954007",   # Prediabetes
            "73211009",   # Family history of diabetes
        ]
        if self._has_any_condition(patient.id, diabetes_codes):
            return True

        # Check Observations for obesity via last BMI
        bmi = self._get_latest_bmi(patient.id)
        if bmi and bmi >= 30.0:
            return True

        return False

    def _is_at_risk_for_cardio(self, patient):
        """
        Example: checks for existing hyperlipidemia condition or smoking status observation.
        """
        hyperlipidemia_codes = [
            "13644009",  # SNOMED: Hyperlipidemia
        ]
        if self._has_any_condition(patient.id, hyperlipidemia_codes):
            return True

        # Check if patient is a current smoker (Observation of tobacco use = 'current')
        if self._is_current_smoker(patient.id):
            return True

        return False

    def _has_borderline_bp(self, patient):
        """
        Check the last BP reading from Observations.
        Consider borderline if systolic 120–129 or diastolic <80, or mild hypertension codes.
        """
        bp = self._get_latest_blood_pressure(patient.id)
        if not bp:
            return False

        systolic = bp.get('systolic')
        diastolic = bp.get('diastolic')

        # Example borderline criteria:
        # Systolic between 120–129, diastolic <80 => borderline
        if systolic is not None and diastolic is not None:
            if 120 <= systolic <= 129 and diastolic < 80:
                return True

        # Alternatively, if they have a Condition for borderline hypertension:
        borderline_codes = ["60423000"]  # SNOMED for borderline hypertension
        if self._has_any_condition(patient.id, borderline_codes):
            return True

        return False

    def _is_eligible_for_lung_screening(self, patient):
        """
        Check if patient has a heavy smoking history (Condition or Observation).
        Example code for 'heavy tobacco smoker' or pack-year data.
        """
        # If patient has Condition "266919005" (Heavy tobacco smoker)
        heavy_smoker_codes = ["266919005"]
        if self._has_any_condition(patient.id, heavy_smoker_codes):
            return True
        # Could also parse Observations for pack-year calculations
        return False

    def _has_any_condition(self, patient_id, code_list):
        """
        Returns True if the patient has ANY Condition with a code in `code_list`.
        """
        for code in code_list:
            # We do partial or exact matches. In real usage, you may want a more robust approach
            found = self._search_condition_by_code(patient_id, code)
            if found:
                return True
        return False

    def _is_current_smoker(self, patient_id):
        """
        Checks Observations for a tobacco use code that indicates current smoker.
        Example SNOMED code for 'Current smoker' = 77176002
        LOINC code for Tobacco smoking status = 72166-2 (which might store a coded value).
        """
        # In real usage, you'd parse the valueCodeableConcept for 'current every day smoker', etc.
        return self._search_observation_value_code(patient_id, "72166-2", ["449868002", "77176002"])

    # -------------------------------------------------------------
    # CONDITION / OBSERVATION QUERIES
    # -------------------------------------------------------------
    def _search_condition_by_code(self, patient_id, code):
        """
        Searches Condition for a given SNOMED or ICD code.
        Returns True if found, False otherwise.
        """
        try:
            search = fhir_condition.Condition.where({
                'subject': f'Patient/{patient_id}',
                'code': code
            })
            bundle = search.perform_resources(self.fhir_client.server)
            if bundle and len(bundle) > 0:
                return True
        except Exception as e:
            logger.error(f"Error searching Condition for code {code}, patient {patient_id}: {e}")
        return False

    def _search_observation_value_code(self, patient_id, loinc_code, answer_codes):
        """
        Example: searches Observations with code=loinc_code and a specific coded value
        in Observation.valueCodeableConcept. If any match an 'answer_code' that indicates
        current smoker, returns True.
        """
        try:
            search = fhir_observation.Observation.where({
                'subject': f'Patient/{patient_id}',
                'code': loinc_code
            })
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for obs in bundle:
                    if not isinstance(obs, fhir_observation.Observation):
                        continue
                    valcc = getattr(obs, 'valueCodeableConcept', None)
                    if valcc and valcc.coding:
                        for coding in valcc.coding:
                            if coding.code in answer_codes:
                                return True
                bundle = bundle.next_bundle()
        except Exception as e:
            logger.error(f"Error searching Observations for code {loinc_code}, patient {patient_id}: {e}")
        return False

    def _get_latest_bmi(self, patient_id):
        """
        Returns the latest BMI value from Observations (LOINC 39156-5 or 60832-3).
        """
        bmi_codes = ["39156-5", "60832-3"]  # LOINC for Body Mass Index
        latest_date = None
        latest_bmi = None

        for code in bmi_codes:
            try:
                search = fhir_observation.Observation.where({
                    'subject': f'Patient/{patient_id}',
                    'code': code
                })
                bundle = search.perform_resources(self.fhir_client.server)
                while bundle:
                    for obs in bundle:
                        if isinstance(obs, fhir_observation.Observation):
                            obs_date = self._extract_obs_effective_date(obs)
                            value = self._extract_quantity_value(obs)
                            if obs_date and value is not None:
                                if not latest_date or obs_date > latest_date:
                                    latest_date = obs_date
                                    latest_bmi = value
                    bundle = bundle.next_bundle()
            except Exception as e:
                logger.error(f"Error retrieving BMI Observations for patient {patient_id}: {e}")

        return latest_bmi

    def _get_latest_blood_pressure(self, patient_id):
        """
        Returns a dict with 'systolic' and 'diastolic' from the latest BP observation
        (LOINC code 85354-9: Blood pressure panel).
        """
        code = "85354-9"
        bp_data = {}
        latest_date = None
        try:
            search = fhir_observation.Observation.where({
                'subject': f'Patient/{patient_id}',
                'code': code
            })
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for obs in bundle:
                    if not isinstance(obs, fhir_observation.Observation):
                        continue
                    obs_date = self._extract_obs_effective_date(obs)
                    if obs_date and (not latest_date or obs_date > latest_date):
                        # Extract components for systolic (8480-6) & diastolic (8462-4)
                        components = getattr(obs, 'component', [])
                        s_val, d_val = None, None
                        for comp in components:
                            coding_list = getattr(comp.code, 'coding', None)
                            if not coding_list:
                                continue
                            for c in coding_list:
                                if c.code == "8480-6":  # Systolic
                                    s_val = self._extract_quantity_value(comp)
                                elif c.code == "8462-4":  # Diastolic
                                    d_val = self._extract_quantity_value(comp)
                        bp_data = {'systolic': s_val, 'diastolic': d_val}
                        latest_date = obs_date
                bundle = bundle.next_bundle()
        except Exception as e:
            logger.error(f"Error retrieving Blood Pressure for patient {patient_id}: {e}")
        return bp_data

    # -------------------------------------------------------------
    # NEEDS-* CHECKS: LOOK FOR LAST SERVICE DATE OR IMMUNIZATION
    # -------------------------------------------------------------
    def _needs_colonoscopy(self, patient_id, now):
        last_date = self._get_last_procedure_date(patient_id, ["73761001"])  # SNOMED for colonoscopy
        if not last_date:
            return True
        return (now.date() - last_date).days > self.colonoscopy_interval

    def _needs_mammogram(self, patient_id, now, interval):
        codes = ["72313002"]  # SNOMED for screening mammogram
        last_date = self._get_last_procedure_date(patient_id, codes)
        if not last_date:
            return True
        return (now.date() - last_date).days > interval

    def _needs_diabetes_screening(self, patient_id, now):
        # E.g. LOINC for A1c or Glucose Tolerance
        codes = ["4548-4", "6298-4"]  # Some LOINC placeholders
        last_date = self._get_last_procedure_date(patient_id, codes)
        if not last_date:
            return True
        return (now.date() - last_date).days > self.diabetes_interval

    def _needs_blood_pressure_check(self, patient_id, now, interval):
        # If no BP reading coded as a Procedure, or if it's older than interval
        # Some places record BP as Observations only, but let's assume you might have a
        # "vitals check" procedure code. We'll just re-use the "85354-9" LOINC for demonstration.
        last_date = self._get_last_procedure_date(patient_id, ["85354-9"])
        if not last_date:
            return True
        return (now.date() - last_date).days > interval

    def _needs_lipid_panel(self, patient_id, now):
        # LOINC for Lipid panel = "24331-1", etc.
        codes = ["24331-1"]
        last_date = self._get_last_procedure_date(patient_id, codes)
        if not last_date:
            return True
        return (now.date() - last_date).days > self.lipid_interval

    def _needs_osteoporosis_screening(self, patient_id, now):
        # SNOMED for DXA = "398181004"
        codes = ["398181004"]
        last_date = self._get_last_procedure_date(patient_id, codes)
        if not last_date:
            return True
        return (now.date() - last_date).days > self.osteoporosis_interval

    def _needs_vision_hearing_screening(self, patient_id, now):
        # SNOMED example code = "424732000"
        codes = ["424732000"]
        last_date = self._get_last_procedure_date(patient_id, codes)
        if not last_date:
            return True
        return (now.date() - last_date).days > self.vision_hearing_interval

    def _needs_cervical_screening(self, patient_id, now, age):
        # Pap test code example: "19762-4" (LOINC) or "Pap" as SNOMED
        # We'll just pick one LOINC for demonstration
        codes = ["19762-4"]
        last_date = self._get_last_procedure_date(patient_id, codes)
        if not last_date:
            return True
        return (now.date() - last_date).days > self.cervical_interval_pap

    def _needs_lung_screening(self, patient_id, now):
        # SNOMED: "168537006" for low-dose CT
        codes = ["168537006"]
        last_date = self._get_last_procedure_date(patient_id, codes)
        if not last_date:
            return True
        return (now.date() - last_date).days > self.lung_interval

    def _needs_shingles_vaccine(self, patient_id):
        # Check if we have an Immunization with relevant code
        # Example: SNOMED for zoster vaccination is "212527006"
        immun_code = ["212527006"]
        last_date = self._get_last_immunization_date(patient_id, immun_code)
        return (last_date is None)

    def _had_recent_preventive_care(self, patient_id, now, interval_days):
        """
        Returns True if the patient had ANY preventive procedure in the last `interval_days`.
        We'll define a broad list of codes for all the services we consider "preventive."
        """
        codes = [
            "73761001",   # Colonoscopy
            "72313002",   # Mammogram
            "4548-4", "6298-4",  # Diabetes screening
            "85354-9",    # BP check
            "24331-1",    # Lipid panel
            "398181004",  # DXA
            "424732000",  # Vision/hearing
            "19762-4",    # Pap
            "168537006",  # Lung screening
        ]
        cutoff = now.date() - timedelta(days=interval_days)

        for code in codes:
            recent = self._has_procedure_after(patient_id, code, cutoff)
            if recent:
                return True

        return False

    # -------------------------------------------------------------
    # FHIR Procedure & Immunization queries
    # -------------------------------------------------------------
    def _get_last_procedure_date(self, patient_id, codes):
        """
        Searches Procedure for any of the given codes, returns the latest date.
        """
        latest_date = None
        for c in codes:
            date_candidate = self._search_procedure_latest(patient_id, c)
            if date_candidate and (not latest_date or date_candidate > latest_date):
                latest_date = date_candidate
        return latest_date

    def _search_procedure_latest(self, patient_id, code):
        """
        Returns the most recent procedure date for `code`.
        """
        latest_date = None
        try:
            search = fhir_procedure.Procedure.where({
                'subject': f'Patient/{patient_id}',
                'code': code
            })
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for proc in bundle:
                    if not isinstance(proc, fhir_procedure.Procedure):
                        continue
                    dt = self._extract_procedure_date(proc)
                    if dt and (not latest_date or dt > latest_date):
                        latest_date = dt
                bundle = bundle.next_bundle()
        except Exception as e:
            logger.error(f"Error searching Procedure for code {code}, patient {patient_id}: {e}")
        return latest_date

    def _extract_procedure_date(self, procedure):
        """
        Extracts a date from procedure.performedDateTime or procedure.performedPeriod.
        Returns a date object or None.
        """
        pdt = getattr(procedure, 'performedDateTime', None)
        pperiod = getattr(procedure, 'performedPeriod', None)

        # performedDateTime is typically an ISO8601 string
        if pdt:
            return self._parse_date_str(pdt)
        if pperiod:
            if pperiod.end:
                return self._parse_date_str(pperiod.end)
            if pperiod.start:
                return self._parse_date_str(pperiod.start)
        return None

    def _get_last_immunization_date(self, patient_id, codes):
        """
        Returns the most recent immunization date for any code in `codes`.
        """
        latest_date = None
        for c in codes:
            date_candidate = self._search_immunization_latest(patient_id, c)
            if date_candidate and (not latest_date or date_candidate > latest_date):
                latest_date = date_candidate
        return latest_date

    def _search_immunization_latest(self, patient_id, code):
        """
        Returns the most recent Immunization date for a code.
        """
        latest_date = None
        try:
            search = fhir_immunization.Immunization.where({
                'patient': f'Patient/{patient_id}',
                'vaccine-code': code
            })
            bundle = search.perform_resources(self.fhir_client.server)
            while bundle:
                for imm in bundle:
                    if not isinstance(imm, fhir_immunization.Immunization):
                        continue
                    dt = getattr(imm, 'occurrenceDateTime', None)
                    if dt:
                        d = self._parse_date_str(dt)
                        if d and (not latest_date or d > latest_date):
                            latest_date = d
                bundle = bundle.next_bundle()
        except Exception as e:
            logger.error(f"Error searching Immunization for code {code}, patient {patient_id}: {e}")
        return latest_date

    def _has_procedure_after(self, patient_id, code, cutoff_date):
        """
        Returns True if there's a Procedure with `code` after `cutoff_date`.
        """
        try:
            search = fhir_procedure.Procedure.where({
                'subject': f'Patient/{patient_id}',
                'code': code,
                'date': f'ge{cutoff_date.isoformat()}'
            })
            bundle = search.perform_resources(self.fhir_client.server)
            if bundle and len(bundle) > 0:
                return True
        except Exception as e:
            logger.error(f"Error checking recent Procedure for code {code}, patient {patient_id}: {e}")
        return False

    # -------------------------------------------------------------
    # OBSERVATION UTILS
    # -------------------------------------------------------------
    def _extract_obs_effective_date(self, obs):
        """
        Extracts the date from Observation.effectiveDateTime or Observation.effectivePeriod.
        """
        edt = getattr(obs, 'effectiveDateTime', None)
        epd = getattr(obs, 'effectivePeriod', None)
        if edt:
            return self._parse_date_str(edt)
        if epd:
            if epd.end:
                return self._parse_date_str(epd.end)
            if epd.start:
                return self._parse_date_str(epd.start)
        return None

    def _extract_quantity_value(self, obj):
        """
        If the Observation or component has a valueQuantity, return the .value as a float.
        """
        valQ = getattr(obj, 'valueQuantity', None)
        if valQ and valQ.value is not None:
            return float(valQ.value)
        return None

    # -------------------------------------------------------------
    # DATE PARSING
    # -------------------------------------------------------------
    def _parse_date_str(self, date_str):
        """
        Attempts to parse a date/time string to a datetime.date.
        """
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.date()
        except ValueError:
            # Possibly just YYYY-MM-DD
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Unable to parse date string: {date_str}")
                return None


# ----------------------------------------------------------------------
# SCRIPT ENTRY POINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Configure logging to console
    logging.basicConfig(level=logging.INFO)

    # Initialize FHIR client and the reminder service
    fhir = get_fhir_client()
    reminder_service = PreventiveCareReminderService(fhir, send_sms)

    # Option 1: Generate a list of due reminders
    # reminders = reminder_service.get_due_reminders()
    # for r in reminders:
    #     print(r)

    # Option 2: Directly process (send) all reminders
    reminder_service.process_reminders()
logger.debug("Preventive care reminder service initialization complete")