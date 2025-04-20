import requests
import json
from django.conf import settings
import logging
import openai
from ..views.utils.constants import OPENAI_MODEL

logger = logging.getLogger(__name__)

class FHIRClient:
    def __init__(self):
        self.base_url = settings.FHIR_SERVER_URL
        self.headers = {
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        }
        self.timeout = settings.FHIR_SERVER_TIMEOUT

    def get_patient_by_phone(self, phone_number):
        """Find patient by phone number"""
        try:
            response = requests.get(
                f"{self.base_url}/Patient",
                params={
                    'telecom': f'phone|{phone_number}'
                },
                headers=self.headers,
                timeout=self.timeout
            )
            if response.status_code == 200:
                bundle = response.json()
                if bundle.get('entry', []):
                    return bundle['entry'][0]['resource']
            return None
        except Exception as e:
            logger.error(f"Error fetching patient by phone: {e}")
            return None

    def get_patient_appointments(self, patient_id):
        """Get patient's appointments"""
        try:
            response = requests.get(
                f"{self.base_url}/Appointment",
                params={
                    'patient': f'Patient/{patient_id}',
                    '_sort': '-date',
                    '_count': '5'
                },
                headers=self.headers,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error fetching appointments: {e}")
            return None

    def get_patient_medications(self, patient_id):
        """Get patient's current medications"""
        try:
            response = requests.get(
                f"{self.base_url}/MedicationStatement",
                params={
                    'subject': f'Patient/{patient_id}',
                    'status': 'active'
                },
                headers=self.headers,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error fetching medications: {e}")
            return None
            
    def search(self, resource_type, params):
        """Generic search method for FHIR resources"""
        try:
            response = requests.get(
                f"{self.base_url}/{resource_type}",
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"FHIR search failed with status {response.status_code}: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Error searching {resource_type}: {e}")
            return None

def detect_intent(text):
    """Detect intents from user input"""
    try:
        # Prepare the prompt for GPT
        prompt = {
            "messages": [
                {"role": "system", "content": "You are a healthcare chatbot assistant. Analyze the user input and identify the intent and entities."},
                {"role": "user", "content": text}
            ]
        }
        
        # Get response from OpenAI
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Identify the intent and entities in this message. Valid intents are: greeting, identifier, set_appointment, cancel_appointment, check_appointments, other."},
                {"role": "user", "content": text}
            ]
        )
        
        # Parse the response
        result = json.loads(response.choices[0].message['content'])
        logger.debug(f"OpenAI GPT response: {result}")
        
        return result.get('intents', [])
    except Exception as e:
        logger.error(f"Error detecting intent: {e}")
        return []


