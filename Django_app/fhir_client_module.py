import logging
import requests
import json
from django.conf import settings  # Import Django settings
from datetime import datetime, timedelta

logger = logging.getLogger('chatbot')

class FHIRClient:
    """
    A client to interact with a FHIR server.
    """

    def __init__(self, base_url=None):
        """
        Initialize the FHIR client with the base URL.
        If base_url is not provided, use settings.FHIR_SERVER_URL
        """
        if base_url is None:
            base_url = settings.FHIR_SERVER_URL  # Use Django settings
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json"
        }
        logger.debug(f"FHIRClient initialized with base URL: {self.base_url}")

    def search(self, resource_type, params=None):
        """
        Search for resources of a specific type with optional query parameters.

        :param resource_type: The FHIR resource type to search (e.g., 'Patient').
        :param params: A dictionary of query parameters.
        :return: JSON response from the FHIR server or None if an error occurs.
        """
        url = f"{self.base_url}/{resource_type}"
        logger.debug(f"Searching for {resource_type} with params: {params} at URL: {url}")
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            logger.debug(f"Search successful for {resource_type}")
            data = response.json()
            logger.debug(f"Search response: {json.dumps(data, indent=2)}")
            return data
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error during search for {resource_type}: {http_err} - Response: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred during search for {resource_type}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception during search for {resource_type}: {req_err}")
        except Exception as e:
            logger.error(f"Unexpected error during search for {resource_type}: {e}", exc_info=True)
        return None

    def read(self, resource_type, resource_id):
        """
        Read a specific resource by type and ID.

        :param resource_type: The FHIR resource type (e.g., 'Patient').
        :param resource_id: The ID of the resource.
        :return: JSON response from the FHIR server or None if an error occurs.
        """
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        logger.debug(f"Reading {resource_type} with ID: {resource_id} at URL: {url}")
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            logger.debug(f"Read successful for {resource_type} ID: {resource_id}")
            data = response.json()
            logger.debug(f"Read response: {json.dumps(data, indent=2)}")
            return data
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error during read for {resource_type} ID {resource_id}: {http_err} - Response: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred during read for {resource_type} ID {resource_id}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception during read for {resource_type} ID {resource_id}: {req_err}")
        except Exception as e:
            logger.error(f"Unexpected error during read for {resource_type} ID {resource_id}: {e}", exc_info=True)
        return None

    def create(self, resource_type, resource_data):
        """
        Create a new resource on the FHIR server.

        :param resource_type: The FHIR resource type to create (e.g., 'Patient').
        :param resource_data: A dictionary representing the resource.
        :return: JSON response from the FHIR server or None if an error occurs.
        """
        url = f"{self.base_url}/{resource_type}"
        logger.debug(f"Creating {resource_type} with data: {json.dumps(resource_data, indent=2)} at URL: {url}")
        try:
            response = requests.post(url, headers=self.headers, json=resource_data, timeout=10)
            response.raise_for_status()
            logger.debug(f"Creation successful for {resource_type}")
            data = response.json()
            logger.debug(f"Creation response: {json.dumps(data, indent=2)}")
            return data
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error during creation of {resource_type}: {http_err} - Response: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred during creation of {resource_type}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception during creation of {resource_type}: {req_err}")
        except Exception as e:
            logger.error(f"Unexpected error during creation of {resource_type}: {e}", exc_info=True)
        return None

    def update(self, resource_type, resource_id, resource_data):
        """
        Update an existing resource on the FHIR server.

        :param resource_type: The FHIR resource type to update (e.g., 'Patient').
        :param resource_id: The ID of the resource to update.
        :param resource_data: A dictionary representing the updated resource.
        :return: JSON response from the FHIR server or None if an error occurs.
        """
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        logger.debug(f"Updating {resource_type} ID: {resource_id} with data: {json.dumps(resource_data, indent=2)} at URL: {url}")
        try:
            response = requests.put(url, headers=self.headers, json=resource_data, timeout=10)
            response.raise_for_status()
            logger.debug(f"Update successful for {resource_type} ID: {resource_id}")
            data = response.json()
            logger.debug(f"Update response: {json.dumps(data, indent=2)}")
            return data
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error during update of {resource_type} ID {resource_id}: {http_err} - Response: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred during update of {resource_type} ID {resource_id}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception during update of {resource_type} ID {resource_id}: {req_err}")
        except Exception as e:
            logger.error(f"Unexpected error during update of {resource_type} ID {resource_id}: {e}", exc_info=True)
        return None

    def delete(self, resource_type, resource_id):
        """
        Delete a resource from the FHIR server.

        :param resource_type: The FHIR resource type to delete (e.g., 'Patient').
        :param resource_id: The ID of the resource to delete.
        :return: True if deletion was successful, False otherwise.
        """
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        logger.debug(f"Deleting {resource_type} ID: {resource_id} at URL: {url}")
        try:
            response = requests.delete(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            logger.debug(f"Deletion successful for {resource_type} ID: {resource_id}")
            return True
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error during deletion of {resource_type} ID {resource_id}: {http_err} - Response: {response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred during deletion of {resource_type} ID {resource_id}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception during deletion of {resource_type} ID {resource_id}: {req_err}")
        except Exception as e:
            logger.error(f"Unexpected error during deletion of {resource_type} ID {resource_id}: {e}", exc_info=True)
        return False


# Add this new function to your existing code
def find_patient_by_email_or_phone(identifier):
    """
    Find a patient by their email or phone number using telecom search.
    
    :param identifier: Email or phone number to search for
    :return: Patient resource or None if not found
    """
    logger.debug(f"Searching for patient with identifier: {identifier}")
    fhir_client = FHIRClient()
    
    # Clean the identifier
    clean_identifier = identifier.strip().lower()
    
    # Try email first
    if '@' in clean_identifier:
        search_params = {
            "telecom": f"email|{clean_identifier}"
        }
        logger.debug(f"Searching by email with params: {search_params}")
        patient_bundle = fhir_client.search("Patient", search_params)
        
        if patient_bundle and 'entry' in patient_bundle and patient_bundle['entry']:
            logger.debug("Patient found by email")
            return patient_bundle['entry'][0]['resource']
    
    # Try phone number
    search_params = {
        "telecom": f"phone|{clean_identifier}"
    }
    logger.debug(f"Searching by phone with params: {search_params}")
    patient_bundle = fhir_client.search("Patient", search_params)
    
    if patient_bundle and 'entry' in patient_bundle and patient_bundle['entry']:
        logger.debug("Patient found by phone")
        return patient_bundle['entry'][0]['resource']
    
    # If no patient found, try searching in identifier system
    search_params = {
        "identifier": clean_identifier
    }
    logger.debug(f"Searching by identifier with params: {search_params}")
    patient_bundle = fhir_client.search("Patient", search_params)
    
    if patient_bundle and 'entry' in patient_bundle and patient_bundle['entry']:
        logger.debug("Patient found by identifier")
        return patient_bundle['entry'][0]['resource']
    
    logger.debug("No patient found with provided identifier")
    return None


def find_patient_by_identifier(identifier):
    """
    Find a patient by their phone number or email.

    :param identifier: The phone number or email to search for.
    :return: Patient resource as a dictionary or None if not found.
    """
    logger.debug(f"Attempting to find patient with identifier: {identifier}")
    fhir_client = FHIRClient()

    # Determine if the identifier is an email or phone number
    if "@" in identifier:
        search_params = {"email": identifier}
    else:
        search_params = {"phone": identifier}

    logger.debug(f"Search parameters: {search_params}")
    patient_bundle = fhir_client.search("Patient", search_params)

    if patient_bundle and 'entry' in patient_bundle and len(patient_bundle['entry']) > 0:
        patient = patient_bundle['entry'][0]['resource']
        logger.debug(f"Patient found: {json.dumps(patient, indent=2)}")
        return patient
    else:
        logger.info(f"No patient found with identifier: {identifier}")
        return None

def get_full_medical_record(patient_id):
    """
    Retrieve the full medical record for a patient.

    :param patient_id: The ID of the patient.
    :return: Dictionary containing all relevant resources or None.
    """
    logger.debug(f"Retrieving full medical record for Patient ID: {patient_id}")
    fhir_client = FHIRClient()

    resources = {}
    # Retrieve Conditions
    conditions = fhir_client.search("Condition", {"patient": patient_id})
    resources['conditions'] = conditions

    # Retrieve Medications
    medications = fhir_client.search("MedicationStatement", {"patient": patient_id})
    resources['medications'] = medications

    # Retrieve Immunizations
    immunizations = fhir_client.search("Immunization", {"patient": patient_id})
    resources['immunizations'] = immunizations

    # Retrieve Procedures
    procedures = fhir_client.search("Procedure", {"patient": patient_id})
    resources['procedures'] = procedures

    # Retrieve Appointments
    appointments = fhir_client.search("Appointment", {"patient": patient_id})
    resources['appointments'] = appointments

    # Add more resources as needed

    logger.debug(f"Full medical record retrieved: {json.dumps(resources, indent=2)}")
    return resources

def get_patient_data(field, patient_id):
    """
    Retrieve specific data for a patient based on the field.

    :param field: The data field to retrieve (e.g., 'height', 'weight', 'conditions', 'medications', 'vaccines').
    :param patient_id: The ID of the patient.
    :return: Formatted string with the requested data or an appropriate message.
    """
    fhir_client = FHIRClient()
    response = ""

    if field == "height":
        observations = fhir_client.search("Observation", {"patient": patient_id, "code": "8302-2"})
        if observations and 'entry' in observations and len(observations['entry']) > 0:
            height = observations['entry'][0]['resource']['valueQuantity']['value']
            response = f"Your height is {height} cm."
        else:
            response = "Height information is not available."

    elif field == "weight":
        observations = fhir_client.search("Observation", {"patient": patient_id, "code": "29463-7"})
        if observations and 'entry' in observations and len(observations['entry']) > 0:
            weight = observations['entry'][0]['resource']['valueQuantity']['value']
            response = f"Your weight is {weight} kg."
        else:
            response = "Weight information is not available."

    elif field == "conditions":
        conditions = fhir_client.search("Condition", {"patient": patient_id, "clinical-status": "active"})
        if conditions and 'entry' in conditions and len(conditions['entry']) > 0:
            condition_list = [entry['resource']['code']['text'] for entry in conditions['entry'] if 'text' in entry['resource']['code']]
            if not condition_list:
                # Fallback to coding display if text is missing
                condition_list = [entry['resource']['code']['coding'][0].get('display', 'Unknown') for entry in conditions['entry']]
            response = "You have the following conditions: " + ", ".join(condition_list) + "."
        else:
            response = "No active conditions found."

    elif field == "medications":
        medications = fhir_client.search("MedicationStatement", {"patient": patient_id, "status": "active"})
        if medications and 'entry' in medications and len(medications['entry']) > 0:
            medication_list = []
            for entry in medications['entry']:
                med = entry['resource'].get('medicationCodeableConcept', {})
                text = med.get('text')
                if text:
                    medication_list.append(text)
                else:
                    # Fallback to coding display if text is missing
                    coding = med.get('coding', [])
                    if coding:
                        medication_list.append(coding[0].get('display', 'Unknown'))
            response = "You are currently taking the following medications: " + ", ".join(medication_list) + "."
        else:
            response = "No active medications found."

    elif field == "vaccines":
        immunizations = fhir_client.search("Immunization", {"patient": patient_id})
        if immunizations and 'entry' in immunizations and len(immunizations['entry']) > 0:
            vaccine_list = []
            for entry in immunizations['entry']:
                vaccine = entry['resource'].get('vaccineCode', {})
                text = vaccine.get('text')
                if text:
                    vaccine_list.append(text)
                else:
                    # Fallback to coding display if text is missing
                    coding = vaccine.get('coding', [])
                    if coding:
                        vaccine_list.append(coding[0].get('display', 'Unknown'))
            response = "You have received the following vaccines: " + ", ".join(vaccine_list) + "."
        else:
            response = "No immunizations found."

    elif field == "practitioner":
        # Retrieve the practitioner's details linked to the patient
        # Assuming each patient has a general practitioner referenced
        patient = fhir_client.read("Patient", patient_id)
        if patient and 'generalPractitioner' in patient:
            practitioner_ref = patient['generalPractitioner'][0]['reference']
            practitioner_id = practitioner_ref.split('/')[-1]
            practitioner = fhir_client.read("Practitioner", practitioner_id)
            if practitioner:
                practitioner_name = f"{practitioner['name'][0]['given'][0]} {practitioner['name'][0]['family']}"
                response = f"Your practitioner is Dr. {practitioner_name}."
            else:
                response = "Your practitioner information is not available."
        else:
            response = "Your practitioner information is not available."

    elif field == "appointments":
        appointments = fhir_client.search("Appointment", {"patient": patient_id, "status": "booked"})
        if appointments and 'entry' in appointments and len(appointments['entry']) > 0:
            appointment_list = []
            for entry in appointments['entry']:
                appt = entry['resource']
                practitioner_ref = next((p['actor']['reference'] for p in appt['participant'] if p['actor']['reference'].startswith('Practitioner/')), None)
                if practitioner_ref:
                    practitioner_id = practitioner_ref.split('/')[-1]
                    practitioner = fhir_client.read("Practitioner", practitioner_id)
                    practitioner_name = f"{practitioner['name'][0]['given'][0]} {practitioner['name'][0]['family']}" if practitioner else "Unknown"
                else:
                    practitioner_name = "Unknown"

                appt_time = appt['start']
                appointment_list.append(f"Appointment with Dr. {practitioner_name} at {appt_time}")

            response = "Your upcoming appointments:\n" + "\n".join(appointment_list)
        else:
            response = "You have no upcoming appointments."

    else:
        response = "I'm not sure how to help with that."

    logger.debug(f"Retrieved data for field '{field}': {response}")
    return response

def set_appointment(patient_id, date_str, time_str, reason):
    """
    Create an appointment for a patient.

    :param patient_id: The ID of the patient.
    :param date_str: The date of the appointment (YYYY-MM-DD).
    :param time_str: The time of the appointment (HH:MM).
    :param reason: The reason for the appointment.
    :return: Confirmation message or an error message.
    """
    fhir_client = FHIRClient()
    
    # Retrieve patient to find their general practitioner
    patient = fhir_client.read("Patient", patient_id)
    if not patient or 'generalPractitioner' not in patient:
        return "Unable to find your general practitioner. Please contact your healthcare provider directly."

    practitioner_ref = patient['generalPractitioner'][0]['reference']
    practitioner_id = practitioner_ref.split('/')[-1]

    # Check practitioner's availability
    # For simplicity, we'll assume that the practitioner has a Schedule resource
    schedules = fhir_client.search("Schedule", {"actor": practitioner_ref})
    if not schedules or 'entry' not in schedules or len(schedules['entry']) == 0:
        return "No available schedules found for your practitioner."

    # For demonstration, pick the first schedule
    schedule = schedules['entry'][0]['resource']
    schedule_id = schedule['id']

    # Check existing appointments for the practitioner at the desired time
    existing_appts = fhir_client.search("Appointment", {
        "practitioner": practitioner_id,
        "start": f"{date_str}T{time_str}:00Z"
    })

    if existing_appts and 'entry' in existing_appts and len(existing_appts['entry']) > 0:
        return "Your practitioner is not available at the requested time. Please choose another time."

    # Create the appointment
    start_datetime = f"{date_str}T{time_str}:00Z"
    end_time = (datetime.strptime(time_str, "%H:%M") + timedelta(hours=1)).strftime("%H:%M")
    end_datetime = f"{date_str}T{end_time}:00Z"

    appointment = {
        "resourceType": "Appointment",
        "status": "booked",
        "description": reason,
        "start": start_datetime,
        "end": end_datetime,
        "participant": [
            {
                "actor": {
                    "reference": f"Patient/{patient_id}"
                },
                "status": "accepted"
            },
            {
                "actor": {
                    "reference": f"Practitioner/{practitioner_id}"
                },
                "status": "accepted"
            }
        ],
        "basedOn": [
            {
                "reference": f"Schedule/{schedule_id}"
            }
        ]
    }

    created_appt = fhir_client.create("Appointment", appointment)
    if created_appt:
        appt_id = created_appt.get('id', 'Unknown')
        return f"Appointment booked with Practitioner ID: {practitioner_id} on {start_datetime} (Appointment ID: {appt_id})."
    else:
        return "Failed to book the appointment. Please try again later."

def cancel_appointment(appointment_id):
    """
    Cancel an existing appointment.

    :param appointment_id: The ID of the appointment to cancel.
    :return: Confirmation message or an error message.
    """
    fhir_client = FHIRClient()
    success = fhir_client.delete("Appointment", appointment_id)
    if success:
        return f"Appointment ID: {appointment_id} has been successfully canceled."
    else:
        return "Failed to cancel the appointment. Please try again later."

def get_practitioner(patient_id):
    """
    Retrieve the practitioner's details linked to the patient.

    :param patient_id: The ID of the patient.
    :return: Practitioner details or None.
    """
    fhir_client = FHIRClient()
    patient = fhir_client.read("Patient", patient_id)
    if patient and 'generalPractitioner' in patient:
        practitioner_ref = patient['generalPractitioner'][0]['reference']
        practitioner_id = practitioner_ref.split('/')[-1]
        practitioner = fhir_client.read("Practitioner", practitioner_id)
        return practitioner
    return None

def get_appointment_availability(practitioner_id, date_str, time_str):
    """
    Check if the practitioner is available at the specified date and time.

    :param practitioner_id: The ID of the practitioner.
    :param date_str: The date of the appointment (YYYY-MM-DD).
    :param time_str: The time of the appointment (HH:MM).
    :return: True if available, False otherwise.
    """
    fhir_client = FHIRClient()
    start_datetime = f"{date_str}T{time_str}:00Z"
    existing_appts = fhir_client.search("Appointment", {
        "practitioner": practitioner_id,
        "start": start_datetime
    })

    if existing_appts and 'entry' in existing_appts and len(existing_appts['entry']) > 0:
        return False
    return True
