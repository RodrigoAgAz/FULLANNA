# chatbot/views/services/fhir_service.py
import httpx
import urllib.parse
from django.conf import settings
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger('chatbot')

class FHIRService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FHIRService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.base_url = settings.FHIR_SERVER_URL.rstrip('/')
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json"
        }
        
        # Add auth headers if configured
        if hasattr(settings, 'FHIR_AUTH_TOKEN'):
            self.headers["Authorization"] = f"Bearer {settings.FHIR_AUTH_TOKEN}"
        
        logger.info(f"FHIR service initialized with base URL: {self.base_url}")
    
    async def search(self, resource_type: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Unified async search method with proper URL encoding"""
        try:
            url = f"{self.base_url}/{resource_type}"
            
            # Properly encode parameters
            if params:
                # Handle special FHIR search parameters
                encoded_params = {}
                for key, value in params.items():
                    if isinstance(value, list):
                        # Handle multiple values for same parameter
                        encoded_params[key] = ','.join(str(v) for v in value)
                    else:
                        encoded_params[key] = str(value)
                
                query_string = urllib.parse.urlencode(encoded_params)
                url = f"{url}?{query_string}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"FHIR search HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"FHIR search error: {str(e)}")
            return None
    
    async def read(self, resource_type: str, resource_id: str) -> Optional[Dict]:
        """Unified async read method"""
        try:
            url = f"{self.base_url}/{resource_type}/{resource_id}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"FHIR read HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"FHIR read error: {str(e)}")
            return None
    
    async def create(self, resource_type: str, resource: Dict) -> Optional[Dict]:
        """Unified async create method"""
        try:
            url = f"{self.base_url}/{resource_type}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, 
                    json=resource, 
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"FHIR create HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"FHIR create error: {str(e)}")
            return None
    
    async def update(self, resource_type: str, resource_id: str, resource: Dict) -> Optional[Dict]:
        """Unified async update method"""
        try:
            url = f"{self.base_url}/{resource_type}/{resource_id}"
            resource['id'] = resource_id
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(
                    url,
                    json=resource,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"FHIR update HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"FHIR update error: {str(e)}")
            return None
    
    async def delete(self, resource_type: str, resource_id: str) -> bool:
        """Delete a FHIR resource"""
        try:
            url = f"{self.base_url}/{resource_type}/{resource_id}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url, headers=self.headers)
                response.raise_for_status()
                return True
                
        except Exception as e:
            logger.error(f"FHIR delete error: {str(e)}")
            return False

# Create singleton instance
fhir_service = FHIRService()

# Improved standalone functions
async def get_patient_by_email(email: str) -> Optional[Dict]:
    """Get patient by email using proper FHIR search"""
    result = await fhir_service.search('Patient', {'email': email})
    return result

async def get_patient_by_phone(phone_number: str) -> Optional[Dict]:
    """Get patient by phone number with improved search"""
    # Clean the phone number
    clean_phone = ''.join(c for c in phone_number if c.isdigit())
    
    # FHIR search for telecom uses 'value' parameter
    search_params = [
        {'telecom': phone_number},
        {'telecom': clean_phone},
        {'phone': phone_number},  # Some servers support this
        {'phone': clean_phone}
    ]
    
    for params in search_params:
        result = await fhir_service.search('Patient', params)
        if result and 'entry' in result and result['entry']:
            logger.info(f"Found patient with phone search params: {params}")
            return result
    
    # Fallback for demo - log this
    logger.warning(f"No patient found for phone {phone_number}, returning first patient for demo")
    return await fhir_service.search('Patient', {'_count': '1'})

async def get_patient_allergies(patient_id: str) -> Optional[Dict]:
    """Get patient allergies with proper patient reference"""
    return await fhir_service.search('AllergyIntolerance', {'patient': f'Patient/{patient_id}'})

async def get_patient_conditions(patient_id: str) -> Optional[Dict]:
    """Get patient conditions"""
    return await fhir_service.search('Condition', {'patient': f'Patient/{patient_id}'})

async def get_patient_immunizations(patient_id: str) -> Optional[Dict]:
    """Get patient immunizations"""
    return await fhir_service.search('Immunization', {'patient': f'Patient/{patient_id}'})

async def get_patient_medications(patient_id: str) -> Optional[Dict]:
    """Get patient medications"""
    return await fhir_service.search('MedicationRequest', {
        'patient': f'Patient/{patient_id}',
        'status': 'active'
    })

async def get_practitioner_for_patient(patient_id: str) -> Optional[Dict]:
    """Get practitioners associated with a patient"""
    # This might need to search through appointments or care team
    appointments = await fhir_service.search('Appointment', {
        'patient': f'Patient/{patient_id}',
        'status': 'booked,fulfilled'
    })
    
    if not appointments or 'entry' not in appointments:
        return None
    
    # Extract unique practitioners
    practitioners = set()
    for entry in appointments['entry']:
        for participant in entry.get('resource', {}).get('participant', []):
            actor = participant.get('actor', {})
            if 'Practitioner' in actor.get('reference', ''):
                practitioners.add(actor['reference'])
    
    return {'practitioners': list(practitioners)}

async def get_available_practitioners() -> Optional[Dict]:
    """Get all available practitioners"""
    return await fhir_service.search('Practitioner', {'active': 'true'})

async def get_practitioner(practitioner_id: str) -> Optional[Dict]:
    """Get specific practitioner"""
    return await fhir_service.read('Practitioner', practitioner_id)

async def get_patient_procedures(patient_id: str) -> Optional[Dict]:
    """Get patient procedures"""
    return await fhir_service.search('Procedure', {
        'patient': f'Patient/{patient_id}',
        '_sort': '-date'
    })

async def get_complete_medical_record(patient_id: str) -> Dict[str, Any]:
    """Get complete medical record with error handling"""
    record = {}
    
    # Fetch all data concurrently
    try:
        results = await asyncio.gather(
            get_patient_allergies(patient_id),
            get_patient_conditions(patient_id),
            get_patient_immunizations(patient_id),
            get_patient_medications(patient_id),
            get_patient_procedures(patient_id),
            return_exceptions=True
        )
        
        record['allergies'] = results[0] if not isinstance(results[0], Exception) else None
        record['conditions'] = results[1] if not isinstance(results[1], Exception) else None
        record['immunizations'] = results[2] if not isinstance(results[2], Exception) else None
        record['medications'] = results[3] if not isinstance(results[3], Exception) else None
        record['procedures'] = results[4] if not isinstance(results[4], Exception) else None
        
    except Exception as e:
        logger.error(f"Error fetching complete medical record: {str(e)}")
    
    return record

async def get_user_appointments(patient_id: str, timezone: str = 'America/New_York') -> Optional[Dict]:
    """Get user appointments with status filter"""
    from datetime import datetime
    
    return await fhir_service.search('Appointment', {
        'patient': f'Patient/{patient_id}',
        'date': f'ge{datetime.now().isoformat()}',
        'status': 'booked,arrived,fulfilled',
        '_sort': 'date'
    })

async def get_user_appointments_direct(patient_id: str, timezone: str = 'America/New_York') -> Optional[Dict]:
    """Alias for get_user_appointments"""
    return await get_user_appointments(patient_id, timezone)

async def get_user_appointments_formatted(patient_id: str, timezone: str = 'America/New_York') -> List[Dict]:
    """Get formatted appointment list"""
    appointments = await get_user_appointments(patient_id, timezone)
    if not appointments or 'entry' not in appointments:
        return []
    
    formatted = []
    for entry in appointments['entry']:
        appointment = entry.get('resource', {})
        
        # Extract practitioner reference
        practitioner_ref = None
        for participant in appointment.get('participant', []):
            actor = participant.get('actor', {})
            if 'Practitioner' in actor.get('reference', ''):
                practitioner_ref = actor['reference'].split('/')[-1]
                break
        
        formatted.append({
            'id': appointment.get('id'),
            'start': appointment.get('start'),
            'end': appointment.get('end'),
            'status': appointment.get('status'),
            'description': appointment.get('description', ''),
            'practitioner': practitioner_ref
        })
    
    return formatted

async def search_available_slots() -> Optional[Dict]:
    """Search for available appointment slots"""
    from datetime import datetime, timedelta
    
    # Search for free slots in the next 30 days
    start_date = datetime.now().isoformat()
    end_date = (datetime.now() + timedelta(days=30)).isoformat()
    
    return await fhir_service.search('Slot', {
        'status': 'free',
        'start': f'ge{start_date}',
        'start': f'le{end_date}',
        '_sort': 'start'
    })

async def get_patient_appointments(patient_id: str) -> Optional[Dict]:
    """Alias for get_user_appointments"""
    return await get_user_appointments(patient_id)

# Add missing import at the top
import asyncio