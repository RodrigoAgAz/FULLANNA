from django.conf import settings

from chatbot.views.services.fhir_service import get_patient_allergies, get_patient_conditions, get_patient_immunizations, get_patient_medications, get_practitioner_for_patient
from ..config import config
from ..utils.formatters import get_resource_name
import logging
import openai
from asgiref.sync import sync_to_async
from fhirclient.models.patient import Patient
from fhirclient.models.condition import Condition
from fhirclient.models.immunization import Immunization
from fhirclient.models.medicationrequest import MedicationRequest
from fhirclient.models.procedure import Procedure
from fhirclient.models.bundle import Bundle
openai.api_key = settings.OPENAI_API_KEY

print ("15")
# Configure logging
logger = logging.getLogger('chatbot')

# Initialize FHIR Client
fhir_client = config.fhir_client
# Initialize Redis client for session management




def format_medications_detailed(medication_entries):
    """
    Formats medication information with detailed dosage and timing.
    
    :param medication_entries: List of medication resources from FHIR server
    :return: Formatted string with medication details
    """
    if not medication_entries:
        return "No active medications found."
    
    try:
        formatted = ["Your current medications:"]
        
        for entry in medication_entries:
            med = entry['resource']
            
            # Get medication name
            med_code = med.get('medicationCodeableConcept', {})
            name = med_code.get('text') or \
                   med_code.get('coding', [{}])[0].get('display', 'Unknown Medication')
            
            formatted.append(f"\n- {name}")
            
            # Get status
            status = med.get('status', 'unknown')
            if status != 'active':
                formatted.append(f"  Status: {status}")
            
            # Process dosage instructions
            dosage_list = med.get('dosage', [])
            if dosage_list:
                for dosage in dosage_list:
                    # Get dose
                    dose_and_rate = dosage.get('doseAndRate', [{}])[0]
                    dose = dose_and_rate.get('doseQuantity', {})
                    dose_value = dose.get('value', '')
                    dose_unit = dose.get('unit', '')
                    if dose_value and dose_unit:
                        formatted.append(f"  Dose: {dose_value} {dose_unit}")
                    
                    # Get timing
                    timing = dosage.get('timing', {})
                    repeat = timing.get('repeat', {})
                    
                    # Frequency
                    frequency = repeat.get('frequency')
                    period = repeat.get('period')
                    period_unit = repeat.get('periodUnit', 'day')
                    if frequency and period:
                        formatted.append(f"  Frequency: {frequency} time(s) per {period} {period_unit}")
                    
                    # Specific times
                    times = repeat.get('timeOfDay', [])
                    if times:
                        formatted.append(f"  Times: {', '.join(times)}")
                    
                    # Route
                    route = dosage.get('route', {}).get('text')
                    if route:
                        formatted.append(f"  Route: {route}")
                    
                    # Additional instructions
                    instructions = dosage.get('patientInstruction')
                    if instructions:
                        formatted.append(f"  Instructions: {instructions}")
                    
                    # Method
                    method = dosage.get('method', {}).get('text')
                    if method:
                        formatted.append(f"  Method: {method}")
            
            # Get reason for medication
            reason_reference = med.get('reasonReference', [])
            if reason_reference:
                reasons = []
                for reason in reason_reference:
                    reason_display = reason.get('display')
                    if reason_display:
                        reasons.append(reason_display)
                if reasons:
                    formatted.append(f"  Reason: {', '.join(reasons)}")
            
            # Get additional notes
            note = med.get('note', [])
            if note:
                notes = [n.get('text') for n in note if n.get('text')]
                if notes:
                    formatted.append(f"  Notes: {' '.join(notes)}")
        
        return "\n".join(formatted)
    
    except Exception as e:
        logger.error(f"Error formatting medications: {str(e)}")
        return "Error formatting medication information."

async def get_complete_medical_record(patient_id, fhir_client):
    try:
        logger.debug(f"Fetching complete medical record for patient {patient_id}")
        
        # Use Patient.read to get patient information
        patient = await sync_to_async(Patient.read)(patient_id, fhir_client.server)
        
        # Use Condition.where to search for conditions
        conditions_bundle = await sync_to_async(Condition.where({
            'patient': patient_id,
            'clinical-status': 'active'
        }).perform)(fhir_client.server)
        
        # Use Immunization.where to search for immunizations
        immunizations_bundle = await sync_to_async(Immunization.where({
            'patient': patient_id,
            '_sort': '-date'
        }).perform)(fhir_client.server)
        
        # Use MedicationRequest.where to search for medications
        medications_bundle = await sync_to_async(MedicationRequest.where({
            'patient': patient_id,
            'status': 'active'
        }).perform)(fhir_client.server)
        
        # Use Procedure.where to search for procedures
        procedures_bundle = await sync_to_async(Procedure.where({
            'patient': patient_id,
            '_sort': '-date'
        }).perform)(fhir_client.server)

        # Now extract and format the data from the bundles
        # Patient information
        name = patient.name[0]
        formatted_name = f"{name.given[0]} {name.family}"

        # Conditions
        conditions = []
        if conditions_bundle.entry:
            for entry in conditions_bundle.entry:
                condition = entry.resource
                condition_name = condition.code.text or condition.code.coding[0].display
                conditions.append(condition_name)

        # Immunizations
        immunizations = []
        if immunizations_bundle.entry:
            for entry in immunizations_bundle.entry:
                immunization = entry.resource
                vaccine_name = immunization.vaccineCode.text or immunization.vaccineCode.coding[0].display
                occurrence_date = immunization.occurrenceDateTime.isostring.split('T')[0]
                immunizations.append(f"{vaccine_name} ({occurrence_date})")

        # Medications
        medications = []
        if medications_bundle.entry:
            for entry in medications_bundle.entry:
                medication_request = entry.resource
                med_code = medication_request.medicationCodeableConcept
                med_name = med_code.text or med_code.coding[0].display
                medications.append(med_name)

        # Procedures
        procedures = []
        if procedures_bundle.entry:
            for entry in procedures_bundle.entry:
                procedure = entry.resource
                proc_code = procedure.code
                proc_name = proc_code.text or proc_code.coding[0].display
                performed_date = procedure.performedDateTime.isostring.split('T')[0] if procedure.performedDateTime else ''
                procedures.append(f"{proc_name} ({performed_date})" if performed_date else proc_name)

        return {
            'name': formatted_name,
            'birthDate': patient.birthDate.isostring,
            'gender': patient.gender,
            'conditions': conditions,
            'immunizations': immunizations,
            'medications': medications,
            'procedures': procedures
        }

    except Exception as e:
        logger.error(f"Error in get_complete_medical_record: {str(e)}", exc_info=True)
        return None
def format_procedures(procedures):
    """
    Formats a list of procedures into a readable string with detailed information.
    
    :param procedures: List of procedure resources from FHIR server
    :return: Formatted string with procedure details
    """
    if not procedures:
        return "No past procedures found."
    
    try:
        formatted = ["Your past procedures:"]
        
        for procedure in procedures:
            # Get procedure name
            code = procedure.get('code', {})
            name = code.get('text') or \
                   code.get('coding', [{}])[0].get('display', 'Unknown Procedure')
            
            # Start new procedure entry
            formatted.append(f"\n- {name}")
            
            # Get performed date/period
            if 'performedDateTime' in procedure:
                performed_date = procedure['performedDateTime'].split('T')[0]
                formatted.append(f"  Date: {performed_date}")
            elif 'performedPeriod' in procedure:
                period = procedure['performedPeriod']
                start = period.get('start', '').split('T')[0]
                end = period.get('end', '').split('T')[0]
                if start == end:
                    formatted.append(f"  Date: {start}")
                else:
                    formatted.append(f"  Period: {start} to {end}")
            
            # Get status
            status = procedure.get('status', '')
            if status:
                formatted.append(f"  Status: {status}")
            
            # Get category
            category = procedure.get('category', {}).get('text')
            if category:
                formatted.append(f"  Category: {category}")
            
            # Get location
            location = procedure.get('location', {}).get('display')
            if location:
                formatted.append(f"  Location: {location}")
            
            # Get performer information
            performers = procedure.get('performer', [])
            if performers:
                performer_names = []
                for performer in performers:
                    actor = performer.get('actor', {})
                    display = actor.get('display')
                    if display:
                        performer_names.append(display)
                if performer_names:
                    formatted.append(f"  Performed by: {', '.join(performer_names)}")
            
            # Get outcome
            outcome = procedure.get('outcome', {}).get('text')
            if outcome:
                formatted.append(f"  Outcome: {outcome}")
            
            # Get complications
            complication = procedure.get('complication', [])
            if complication:
                complications = []
                for comp in complication:
                    comp_text = comp.get('text') or comp.get('coding', [{}])[0].get('display')
                    if comp_text:
                        complications.append(comp_text)
                if complications:
                    formatted.append(f"  Complications: {', '.join(complications)}")
            
            # Get follow-up
            follow_up = procedure.get('followUp', [])
            if follow_up:
                followups = []
                for fu in follow_up:
                    fu_text = fu.get('text') or fu.get('coding', [{}])[0].get('display')
                    if fu_text:
                        followups.append(fu_text)
                if followups:
                    formatted.append(f"  Follow-up: {', '.join(followups)}")
            
            # Get notes
            notes = procedure.get('note', [])
            if notes:
                note_texts = [note.get('text') for note in notes if note.get('text')]
                if note_texts:
                    formatted.append(f"  Notes: {' '.join(note_texts)}")
        
        return "\n".join(formatted)
    
    except Exception as e:
        logger.error(f"Error formatting procedures: {str(e)}")
        return "Error formatting procedure information."

def format_conditions(conditions):
    """
    Formats a list of conditions into a readable string.
    """
    if not conditions:
        return "No active conditions found."
    
    formatted = ["Your current conditions:"]
    for condition in conditions:
        try:
            # Get condition details
            name = condition.get('code', {}).get('text') or \
                   condition.get('code', {}).get('coding', [{}])[0].get('display', 'Unknown Condition')
            
            # Get severity if available
            severity = condition.get('severity', {}).get('text', '')
            severity_str = f" ({severity})" if severity else ""
            
            # Get onset date if available
            onset = condition.get('onsetDateTime', '').split('T')[0] if condition.get('onsetDateTime') else ''
            onset_str = f" - diagnosed on {onset}" if onset else ""
            
            # Get clinical status
            clinical_status = condition.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', 'unknown')
            status_str = f" - {clinical_status}" if clinical_status != 'unknown' else ""
            
            formatted.append(f"- {name}{severity_str}{status_str}{onset_str}")
            
            # Add notes if available
            notes = condition.get('note', [])
            for note in notes:
                if note.get('text'):
                    formatted.append(f"  Note: {note['text']}")
                    
        except Exception as e:
            logger.error(f"Error formatting condition: {e}")
            formatted.append(f"- Error formatting condition")
    
    return "\n".join(formatted)
print ("16")