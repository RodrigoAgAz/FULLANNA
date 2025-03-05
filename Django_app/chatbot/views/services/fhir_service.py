# chatbot/views/services/fhir_service.py
# chatbot/views/services/fhir_service.py

from django.conf import settings
from fhirclient import client
from chatbot.views.utils.shared import get_resource_name
from datetime import datetime
from zoneinfo import ZoneInfo
import urllib.parse
import logging
from asgiref.sync import sync_to_async
import requests
import httpx

# Configure logging
logger = logging.getLogger('chatbot')
print ("22")
# Initialize FHIR Client
def get_fhir_client():
    """Get a configured FHIR client instance"""
    settings_dict = {
        'app_id': 'anna_chatbot',  # Replace with your actual app ID
        'api_base': settings.FHIR_SERVER_URL
    }
    try:
        fhir_server = client.FHIRClient(settings=settings_dict).server
        logger.info("FHIR server initialized successfully")
        return fhir_server  # Return server instance which has request_json method
    except Exception as e:
        logger.error(f"Failed to initialize FHIR server: {e}")
        raise

# Initialize global FHIR client with the server object
def get_fhir_server():
    """Get FHIR server instance with proper configuration"""
    settings_dict = {
        'app_id': 'anna_chatbot',
        'api_base': settings.FHIR_SERVER_URL
    }
    try:
        smart = client.FHIRClient(settings=settings_dict)
        logger.info("FHIR server initialized successfully")
        return smart.server  # Return the server object that has request_json
    except Exception as e:
        logger.error(f"Failed to initialize FHIR server: {e}")
        raise

# Initialize global FHIR server
fhir_server = get_fhir_server()

# Add all these standalone functions
async def get_patient_by_email(email):
    fhir_service = FHIRService()
    result = await fhir_service.search('Patient', {'email': email})
    return result

async def get_patient_allergies(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_patient_allergies(patient_id)

async def get_patient_conditions(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_patient_conditions(patient_id)

async def get_patient_immunizations(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_patient_immunizations(patient_id)

async def get_patient_medications(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_patient_medications(patient_id)

async def get_practitioner_for_patient(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_practitioner_for_patient(patient_id)

async def get_available_practitioners():
    fhir_service = FHIRService()
    return await fhir_service.get_available_practitioners()

async def get_practitioner(practitioner_id):
    fhir_service = FHIRService()
    return await fhir_service.get_practitioner(practitioner_id)

async def get_patient_procedures(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_patient_procedures(patient_id)

async def get_complete_medical_record(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_complete_medical_record(patient_id)

async def get_user_appointments(patient_id, timezone='America/New_York'):
    fhir_service = FHIRService()
    return await fhir_service.get_user_appointments(patient_id, timezone)

async def get_user_appointments_direct(patient_id, timezone='America/New_York'):
    fhir_service = FHIRService()
    return await fhir_service.get_user_appointments_direct(patient_id, timezone)

async def get_user_appointments_formatted(patient_id, timezone='America/New_York'):
    fhir_service = FHIRService()
    return await fhir_service.get_user_appointments_formatted(patient_id, timezone)

async def search_available_slots(fhir_client):
    fhir_service = FHIRService()
    return await fhir_service.search_available_slots(fhir_client)

async def get_patient_appointments(patient_id):
    fhir_service = FHIRService()
    return await fhir_service.get_patient_appointments(patient_id)

class FHIRService:
    def __init__(self):
        self.base_url = settings.FHIR_SERVER_URL
        self.fhir_client = fhir_server
        self.logger = logging.getLogger('chatbot')
        self.fhir_client = get_fhir_client()

    async def search(self, resource_type, params=None):
        """Perform asynchronous FHIR search"""
        try:
            search_path = f"{resource_type}"
            if params:
                param_str = "&".join(f"{k}={v}" for k, v in params.items())
                search_path = f"{search_path}?{param_str}"
            
            logger.debug(f"FHIR search path: {search_path}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{search_path}",
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.TimeoutException:
            logger.error(f"FHIR search timeout for {search_path}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"FHIR search HTTP error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"FHIR search error: {str(e)}")
            return None

    def get_practitioner_name(self, resource):
        """Extracts practitioner's full name using the get_resource_name utility."""
        try:
            return get_resource_name(resource)
        except Exception as e:
            self.logger.error(f"Error getting practitioner name: {str(e)}")
            return "Unknown"

    def get_practitioner_specialty(self, resource):
        """Extracts practitioner's specialties from the resource."""
        try:
            qualifications = resource.get('qualification', [])
            specialties = []
            for qual in qualifications:
                code = qual.get('code', {})
                display = (code.get('text') or 
                          code.get('coding', [{}])[0].get('display'))
                if display:
                    specialties.append(display)
            return ', '.join(specialties) if specialties else 'General Practice'
        except Exception as e:
            self.logger.error(f"Error extracting practitioner specialty: {str(e)}")
            return 'General Practice'

    def get_patient(self, patient_id):
        """Get patient by ID"""
        try:
            patient = self.fhir_client.read("Patient", patient_id)
            self.logger.debug(f"Retrieved patient: {patient}")
            return patient
        except Exception as e:
            self.logger.error(f"Error retrieving patient {patient_id}: {str(e)}")
            return None

    async def get_patient_by_email(self, email: str):
        """Get patient by email"""
        try:
            search_params = {'telecom:contains': email}
            result = await self.search('Patient', search_params)  # Make sure this is awaited
            
            if result and 'entry' in result:
                return result['entry'][0]['resource']
            return None
            
        except Exception as e:
            logger.error(f"Error getting patient by email: {str(e)}")
            return None

    def get_patient_by_phone(self, phone_number):
        """Retrieves a patient resource from the FHIR server based on phone number."""
        try:
            self.logger.debug(f"Searching for patient with phone number: {phone_number}")
            
            search_params = [
                {"telecom": f"phone|{urllib.parse.quote(phone_number)}"},
                {"telecom": phone_number}
            ]

            for params in search_params:
                try:
                    # Construct search query
                    query_string = '&'.join(f'{k}={v}' for k, v in params.items())
                    path = f"Patient?{query_string}"
                    result = self.fhir_client.request_json(path)
                    
                    if result and 'entry' in result and result['entry']:
                        patient = result['entry'][0]['resource']
                        self.logger.debug(f"Found patient: {patient}")
                        return patient
                except Exception as search_error:
                    self.logger.debug(f"Search attempt failed: {str(search_error)}")
                    continue

            self.logger.debug("No patient found with the given phone number.")
            return None

        except Exception as e:
            self.logger.error(f"Error retrieving patient by phone: {e}")
            return None

    def get_practitioner_for_patient(self, patient):
        """Retrieves the practitioner's information linked to the patient."""
        try:
            general_practitioners = patient.get('generalPractitioner', [])
            if general_practitioners:
                practitioner_ref = general_practitioners[0].get('reference')
                if practitioner_ref:
                    practitioner_id = practitioner_ref.split('/')[-1]
                    practitioner = self.fhir_client.read("Practitioner", practitioner_id)
                    if practitioner:
                        self.logger.debug(f"Practitioner found: {practitioner.get('id')}")
                        return practitioner
            self.logger.debug("No practitioner linked to the patient.")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving practitioner for patient: {str(e)}")
            return None

    async def get_user_appointments(self, patient_id, timezone='America/New_York'):
        """Get user appointments with detailed logging"""
        self.logger.debug(f"Starting get_user_appointments for patient {patient_id}")
        self.logger.debug(f"Using timezone: {timezone}")
        
        try:
            search_params = {
                'patient': f'Patient/{patient_id}',
                'status': 'booked,arrived,fulfilled'
            }
            self.logger.debug(f"Search parameters: {search_params}")
            
            appointments = await self.search('Appointment', search_params)
            self.logger.debug(f"Raw appointments response: {appointments}")
            
            if not appointments:
                self.logger.debug("No appointments found")
                return []

            formatted_appointments = []
            for entry in appointments.get('entry', []):
                appt = entry.get('resource', {})
                
                try:
                    # Get appointment details
                    start_time = datetime.fromisoformat(appt.get('start').replace('Z', '+00:00'))
                    local_time = start_time.astimezone(ZoneInfo(timezone))
                    
                    # Get practitioner details
                    practitioner_ref = None
                    for participant in appt.get('participant', []):
                        actor = participant.get('actor', {})
                        if actor.get('type') == 'Practitioner' or 'Practitioner/' in actor.get('reference', ''):
                            practitioner_ref = actor.get('reference')
                            break
                    
                    practitioner_name = "Unknown Provider"
                    if practitioner_ref:
                        practitioner_id = practitioner_ref.split('/')[-1]
                        practitioner = await self.read("Practitioner", practitioner_id)
                        if practitioner:
                            name = self.get_practitioner_name(practitioner)
                            specialty = self.get_practitioner_specialty(practitioner)
                            practitioner_name = f"{name} ({specialty})" if specialty != 'Unknown specialty' else name
                    
                    formatted_appointments.append({
                        'datetime': local_time.strftime("%A, %B %d%S at %I:%M %p"),
                        'practitioner': practitioner_name,
                        'status': appt.get('status', 'unknown'),
                        'id': appt.get('id'),
                        'description': appt.get('description', 'General appointment')
                    })
                except Exception as e:
                    self.logger.error(f"Error formatting appointment: {e}")
                    continue
                
            return sorted(formatted_appointments, key=lambda x: x['datetime'])
            
        except Exception as e:
            self.logger.error(f"Error getting appointments: {e}")
            return []

    async def get_patient_immunizations(self, patient_id):
        """
        Retrieves immunization history for a patient from the FHIR server.
        
        :param patient_id: The patient's FHIR resource ID
        :return: List of immunization resources or empty list if none found
        """
        try:
            self.logger.debug(f"Retrieving immunizations for patient ID: {patient_id}")
            
            # Search for Immunization resources
            search_params = {
                "patient": f"Patient/{patient_id}",
                "_sort": "-date"  # Sort by date in descending order
            }
            
            immunization_result = await self.search("Immunization", search_params)
            
            if immunization_result and 'entry' in immunization_result:
                immunizations = []
                for entry in immunization_result['entry']:
                    immunization = entry['resource']
                    
                    # Format each immunization with relevant information
                    formatted_immunization = {
                        'vaccineCode': {
                            'text': immunization.get('vaccineCode', {}).get('text') or 
                                   immunization.get('vaccineCode', {}).get('coding', [{}])[0].get('display', 'Unknown vaccine')
                        },
                        'occurrenceDateTime': immunization.get('occurrenceDateTime', ''),
                        'status': immunization.get('status', 'unknown'),
                        'doseNumber': immunization.get('protocolApplied', [{}])[0].get('doseNumber', ''),
                        'seriesDoses': immunization.get('protocolApplied', [{}])[0].get('seriesDoses', ''),
                        'manufacturer': immunization.get('manufacturer', {}).get('display', ''),
                        'lotNumber': immunization.get('lotNumber', ''),
                        'performer': [
                            {
                                'actor': {
                                    'display': perf.get('actor', {}).get('display', 'Unknown provider')
                                }
                            } for perf in immunization.get('performer', [])
                        ],
                        'note': [
                            {'text': note.get('text', '')} 
                            for note in immunization.get('note', [])
                        ]
                    }
                    
                    immunizations.append(formatted_immunization)
                
                self.logger.debug(f"Found {len(immunizations)} immunizations for patient")
                return immunizations
            
            self.logger.debug("No immunizations found for patient")
            return []
            
        except Exception as e:
            self.logger.error(f"Error retrieving patient immunizations: {e}")
            return []

    def get_patient_name(self, patient_resource):
        """Extracts patient's full name"""
        try:
            names = patient_resource.get('name', [])
            if not names:
                return "Patient"
            name = names[0]
            given = ' '.join(name.get('given', []))
            family = name.get('family', '')
            full_name = f"{given} {family}".strip()
            return full_name if full_name else "Patient"
        except Exception as e:
            self.logger.error(f"Error extracting patient name: {e}")
            return "Patient"

    async def get_patient_conditions(self, patient_id):
        """
        Retrieves active conditions for a patient from the FHIR server and formats them.
        
        Args:
            patient_id (str): The patient's FHIR resource ID
            
        Returns:
            list: List of formatted condition strings
        """
        try:
            self.logger.debug(f"Retrieving conditions for patient ID: {patient_id}")
            
            search_params = {
                "patient": f"Patient/{patient_id}",
                "clinical-status": "active",
                "_sort": "-recorded-date"  # Sort by most recently recorded first
            }
            
            conditions = await self.search("Condition", search_params)
            
            if not conditions or 'entry' not in conditions:
                self.logger.debug(f"No conditions found for patient {patient_id}")
                return ["No current medical conditions found."]
                
            formatted_conditions = ["Current Medical Conditions:"]
            for entry in conditions['entry']:
                condition = entry['resource']
                try:
                    # Extract condition details
                    name = condition.get('code', {}).get('text') or \
                           (condition.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown condition')
                    
                    clinical_status_obj = condition.get('clinicalStatus', {})
                    clinical_status = clinical_status_obj.get('text') or \
                                      (clinical_status_obj.get('coding', [{}])[0].get('display') or 'Unknown status')
                    
                    verification_obj = condition.get('verificationStatus', {})
                    verification_status = verification_obj.get('text') or \
                                          (verification_obj.get('coding', [{}])[0].get('display') or 'Unknown verification')
                    
                    onset_date = condition.get('onsetDateTime') or condition.get('onsetPeriod', {}).get('start') or condition.get('onsetString', 'Unknown onset')
                    onset_date = onset_date.split('T')[0] if isinstance(onset_date, str) else 'Unknown onset'
                    
                    condition_line = f"- {name} (Status: {clinical_status}, Verification: {verification_status}, Onset: {onset_date})"
                    
                    # Add condition notes if available
                    notes = condition.get('note', [])
                    for note in notes:
                        note_text = note.get('text', '')
                        if note_text:
                            condition_line += f"\n  Note: {note_text}"
                    
                    formatted_conditions.append(condition_line)
                except Exception as e:
                    self.logger.error(f"Error formatting condition: {e}")
                    continue
            
            return formatted_conditions
                
        except Exception as e:
            self.logger.error(f"Error fetching conditions: {e}", exc_info=True)
            return ["Error retrieving medical conditions."]

    async def get_patient_medications(self, patient_id):
        """Retrieves active medications for the given patient and formats them."""
        try:
            self.logger.debug(f"Retrieving medications for patient ID: {patient_id}")
            
            search_params = {
                "patient": f"Patient/{patient_id}",
                "status": "active"
            }
            
            medication_statements = await self.search("MedicationStatement", search_params)
            medication_requests = await self.search("MedicationRequest", search_params)
            
            medications = []
            
            # Process MedicationStatements
            if medication_statements and 'entry' in medication_statements:
                for entry in medication_statements['entry']:
                    med = entry['resource']
                    name = med.get('medicationCodeableConcept', {}).get('text') or \
                           (med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display') or 'Unknown medication')
                    dosage = med.get('dosage', [{}])[0].get('text', 'No dosage information')
                    medications.append(f"- {name} ({dosage})")
            
            # Process MedicationRequests
            if medication_requests and 'entry' in medication_requests:
                for entry in medication_requests['entry']:
                    med = entry['resource']
                    name = med.get('medicationCodeableConcept', {}).get('text') or \
                           (med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display') or 'Unknown medication')
                    dosage = med.get('dosageInstruction', [{}])[0].get('text', 'No dosage information')
                    medications.append(f"- {name} ({dosage})")
            
            if medications:
                formatted_meds = ["Current Medications:"]
                formatted_meds.extend(medications)
                return formatted_meds
            
            self.logger.debug("No active medications found for patient.")
            return ["No active medications found."]
                
        except Exception as e:
            self.logger.error(f"Error fetching medications: {e}", exc_info=True)
            return ["Error retrieving medications."]

    async def get_patient_allergies(self, patient_id):
        """
        Retrieves allergy information for a patient from the FHIR server and formats it.
        
        :param patient_id: The patient's FHIR resource ID
        :return: List of formatted allergy strings or a message if none found
        """
        try:
            self.logger.debug(f"Retrieving allergies for patient ID: {patient_id}")
            
            search_params = {
                "patient": f"Patient/{patient_id}",
                "clinical-status": "active"
            }
            
            allergy_result = await self.search("AllergyIntolerance", search_params)
            
            if allergy_result and 'entry' in allergy_result:
                allergies = []
                for entry in allergy_result['entry']:
                    allergy = entry['resource']
                    try:
                        # Extract allergy details
                        code = allergy.get('code', {}).get('text') or \
                               (allergy.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown substance')
                        
                        reactions = allergy.get('reaction', [])
                        reaction_details = []
                        for reaction in reactions:
                            manifestation = reaction.get('manifestation', [{}])[0].get('text') or \
                                            (reaction.get('manifestation', [{}])[0].get('coding', [{}])[0].get('display') or 'Unknown reaction')
                            severity = reaction.get('severity', 'unknown')
                            reaction_details.append(f"{manifestation} (Severity: {severity})")
                        
                        reaction_str = '; '.join(reaction_details) if reaction_details else 'No reaction details'
                        
                        allergy_line = f"- {code}: {reaction_str}"
                        
                        # Add allergy notes if available
                        notes = allergy.get('note', [])
                        for note in notes:
                            note_text = note.get('text', '')
                            if note_text:
                                allergy_line += f"\n  Note: {note_text}"
                        
                        allergies.append(allergy_line)
                    except Exception as e:
                        self.logger.error(f"Error formatting allergy: {e}")
                        continue
                
                formatted_allergies = ["Active Allergies:"]
                formatted_allergies.extend(allergies)
                return formatted_allergies
            
            self.logger.debug("No active allergies found for patient.")
            return ["No active allergies found."]
                
        except Exception as e:
            self.logger.error(f"Error retrieving patient allergies: {e}", exc_info=True)
            return ["Error retrieving allergies."]

    async def get_patient_procedures(self, patient_id):
        """Retrieves past procedures for the patient and formats them."""
        try:
            self.logger.debug(f"Retrieving procedures for patient ID: {patient_id}")
            
            search_params = {
                "patient": f"Patient/{patient_id}",
                "status": "completed",
                "_sort": "-recorded-date"  # Sort by most recently recorded first
            }
            
            procedures = await self.search("Procedure", search_params)
            
            if not procedures or 'entry' not in procedures:
                self.logger.debug("No procedures found for patient.")
                return ["No past procedures found."]
            
            formatted_procedures = ["Past Procedures:"]
            for entry in procedures['entry']:
                procedure = entry['resource']
                try:
                    # Extract procedure details
                    name = procedure.get('code', {}).get('text') or \
                           (procedure.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown procedure')
                    
                    date = procedure.get('performedDateTime') or procedure.get('performedPeriod', {}).get('start') or 'Unknown date'
                    date = date.split('T')[0] if isinstance(date, str) else 'Unknown date'
                    
                    status = procedure.get('status', 'unknown')
                    
                    procedure_line = f"- {name} on {date} (Status: {status})"
                    
                    # Add procedure notes if available
                    notes = procedure.get('note', [])
                    for note in notes:
                        note_text = note.get('text', '')
                        if note_text:
                            procedure_line += f"\n  Note: {note_text}"
                    
                    formatted_procedures.append(procedure_line)
                except Exception as e:
                    self.logger.error(f"Error formatting procedure: {e}")
                    continue
            
            return formatted_procedures
                
        except Exception as e:
            self.logger.error(f"Error fetching procedures: {e}", exc_info=True)
            return ["Error retrieving procedures."]
        
    async def read(self, resource_type, resource_id):
        """Async wrapper for FHIR read"""
        try:
            path = f"{resource_type}/{resource_id}"
            request_json_async = sync_to_async(
                self.fhir_client.request_json,
                thread_sensitive=False
            )
            result = await request_json_async(path)
            return result
        except Exception as e:
            self.logger.error(f"FHIR read error for {resource_type}/{resource_id}: {str(e)}")
            return None

    async def get_available_practitioners(self):
        """Get list of available practitioners"""
        self.logger.debug("Starting get_available_practitioners")
        try:
            self.logger.debug("Attempting to search for practitioners")
            practitioners = await self.search('Practitioner', {})
            self.logger.debug(f"Raw practitioners response: {practitioners}")
            
            if practitioners and 'entry' in practitioners:
                available_practitioners = []
                self.logger.debug(f"Found {len(practitioners['entry'])} practitioners")
                
                for entry in practitioners['entry']:
                    self.logger.debug(f"Processing practitioner entry: {entry}")
                    practitioner = entry['resource']
                    
                    # Log practitioner details
                    self.logger.debug(f"Practitioner ID: {practitioner.get('id')}")
                    self.logger.debug(f"Practitioner resource: {practitioner}")
                    
                    # Get practitioner role and specialty from extensions
                    role = None
                    specialty = None
                    for extension in practitioner.get('extension', []):
                        if extension['url'].endswith('practitioner-role'):
                            role = extension.get('valueString')
                        elif extension['url'].endswith('practitioner-specialty'):
                            specialty = extension.get('valueString')
                    
                    name = self.get_practitioner_name(practitioner)
                    available_practitioners.append({
                        'id': practitioner['id'],
                        'name': name,
                        'role': role or 'General Practitioner',
                        'specialty': specialty or 'General Practice'
                    })
                
                self.logger.debug(f"Final available practitioners: {available_practitioners}")
                return available_practitioners
            
            self.logger.debug("No practitioners found in response")
            return []
            
        except Exception as e:
            self.logger.error(f"Error in get_available_practitioners: {str(e)}")
            self.logger.error("Full error details:", exc_info=True)
            self.logger.error(f"FHIR client state: {self.fhir_client}")
            return []

    async def get_user_appointments_direct(self, patient_id, timezone='America/New_York'):
        """Alternative method to get user appointments directly"""
        return await self.get_user_appointments(patient_id, timezone)

    async def get_complete_medical_record(self, patient_id):
        """Fetches and formats the complete medical record for a patient."""
        try:
            self.logger.debug(f"Fetching complete medical record for patient ID: {patient_id}")
            
            # Personal Information
            patient = await self.read("Patient", patient_id)
            if not patient:
                self.logger.error("Patient record not found.")
                return None
            
            record = []
            record.append("BASIC INFORMATION:")
            name = self.get_patient_name(patient)
            record.append(f"Name: {name}")
            record.append(f"Gender: {patient.get('gender', 'Not specified')}")
            record.append(f"Birth Date: {patient.get('birthDate', 'Not specified')}")
            
            # Contact Information
            record.append("\nCONTACT INFORMATION:")
            for telecom in patient.get('telecom', []):
                system = telecom.get('system', '').title()
                value = telecom.get('value', '')
                record.append(f"{system}: {value}")
            
            # Address
            if patient.get('address'):
                address = patient['address'][0]
                address_str = ', '.join(filter(None, [
                    ', '.join(address.get('line', [])),
                    address.get('city', ''),
                    address.get('state', ''),
                    address.get('postalCode', ''),
                    address.get('country', '')
                ]))
                record.append(f"Address: {address_str}")
            
            # Health Metrics
            record.append("\nHEALTH METRICS:")
            for extension in patient.get('extension', []):
                if extension['url'].endswith('height'):
                    value = extension.get('valueQuantity', {})
                    record.append(f"Height: {value.get('value')} {value.get('unit')}")
                elif extension['url'].endswith('weight'):
                    value = extension.get('valueQuantity', {})
                    record.append(f"Weight: {value.get('value')} {value.get('unit')}")
            
            # Medical Conditions
            conditions = await self.get_patient_conditions(patient_id)
            record.extend(conditions)
            
            # Medications
            medications = await self.get_patient_medications(patient_id)
            record.extend(medications)
            
            # Past Procedures
            procedures = await self.get_patient_procedures(patient_id)
            record.extend(procedures)
            
            # Immunizations
            immunizations = await self.get_patient_immunizations(patient_id)
            if immunizations:
                record.append("\nIMMUNIZATIONS:")
                for imm in immunizations:
                    imm_line = f"- {imm['vaccineCode']['text']} on {imm['occurrenceDateTime']} (Status: {imm['status']})"
                    if imm.get('note'):
                        for note in imm['note']:
                            if note.get('text'):
                                imm_line += f"\n  Note: {note['text']}"
                    record.append(imm_line)
            else:
                record.append("\nIMMUNIZATIONS:")
                record.append("No immunization records found.")
            
            self.logger.debug("Complete medical record fetched successfully.")
            return "\n".join(record)
                
        except Exception as e:
            self.logger.error(f"Error fetching complete medical record: {e}", exc_info=True)
            return None

    async def get_user_appointments_formatted(self, patient_id, timezone='America/New_York'):
        """Fetches and formats user appointments for display."""
        try:
            appointments = await self.get_user_appointments(patient_id, timezone)
            if not appointments:
                return ["You don't have any upcoming appointments scheduled."]
            
            messages = ["Here are your upcoming appointments:"]
            for appt in appointments:
                messages.append(f"- {appt['datetime']} with {appt['practitioner']} ({appt['description']})")
            
            return messages
        except Exception as e:
            self.logger.error(f"Error formatting user appointments: {e}", exc_info=True)
            return ["Error retrieving appointments."]

    async def get_diagnostic_reports(self, search_params):
        """Get diagnostic reports (lab results) for a patient"""
        try:
            result = await self.search('DiagnosticReport', search_params)
            
            if result and 'entry' in result:
                return result['entry']
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting diagnostic reports: {str(e)}")
            return []

    async def get_lab_results(self, patient_id):
        """Fetch lab results for a patient"""
        try:
            # Try multiple category codes that might represent lab results
            categories = ['laboratory', 'LAB', 'lab']
            results = None
            
            for category in categories:
                # Build the FHIR query for DiagnosticReport
                query = (
                    f"/DiagnosticReport?patient={patient_id}"
                    f"&category={category}"
                    "&_sort=-date"
                    "&_include=DiagnosticReport:result"
                    "&_include=DiagnosticReport:subject"
                )
                
                # Make the request
                response = await self._make_request('GET', query)
                logger.debug(f"FHIR response for category {category}: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('total', 0) > 0:
                        results = data
                        break
            
            # If no results found through categories, try without category filter
            if not results:
                query = (
                    f"/DiagnosticReport?patient={patient_id}"
                    "&_sort=-date"
                    "&_include=DiagnosticReport:result"
                    "&_include=DiagnosticReport:subject"
                )
                response = await self._make_request('GET', query)
                if response.status_code == 200:
                    results = response.json()
            
            return results
                
        except Exception as e:
            logger.error(f"Error in get_lab_results: {str(e)}")
            return None

    async def get_lab_reference_ranges(self, test_code):
        """Get reference ranges for a specific lab test"""
        try:
            params = {
                'code': test_code,
                'category': 'laboratory'
            }
            return await self.search('ObservationDefinition', params)
        except Exception as e:
            self.logger.error(f"Error fetching reference ranges: {str(e)}")
            raise

print ("23")