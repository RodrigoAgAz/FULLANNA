from datetime import datetime
from django.conf import settings
from django.urls import resolve
from django.http import HttpRequest
from chatbot.views.config import config as app_config
import json
import logging

logger = logging.getLogger('chatbot')

# Use app_config instead of config
fhir_client = app_config.fhir_client

def get_resource_name(resource):
    """Get the display name of a FHIR resource."""
    if not resource:
        return "Unknown"
    
    if resource.get('name'):
        names = resource['name']
        if isinstance(names, list) and names:
            name = names[0]
            if isinstance(name, dict):
                return name.get('text') or f"{name.get('given', [''])[0]} {name.get('family', '')}"
        elif isinstance(names, dict):
            return names.get('text') or f"{names.get('given', [''])[0]} {names.get('family', '')}"
    
    return f"{resource.get('resourceType', 'Unknown')} {resource.get('id', 'Unknown')}"

def format_medications(medications_entries):
    """Format medications for display"""
    formatted = []
    for entry in medications_entries:
        med = entry.get('resource', {})
        if med:
            medication_name = med.get('medicationCodeableConcept', {}).get('text', 'Unknown Medication')
            dosage = med.get('dosageInstruction', [{}])[0]
            dose = dosage.get('doseAndRate', [{}])[0].get('doseQuantity', {})
            timing = dosage.get('timing', {}).get('repeat', {})
            
            med_str = f"- {medication_name}"
            if dose:
                med_str += f" {dose.get('value', '')} {dose.get('unit', '')}"
            if timing:
                med_str += f" {timing.get('frequency', '')} times per {timing.get('period', '')} {timing.get('periodUnit', '')}"
            
            formatted.append(med_str)
    
    return "\n".join(formatted) if formatted else "No medications found"

def format_appointments(appointment_entries):
    """Format appointments for display"""
    formatted = []
    for entry in appointment_entries:
        appt = entry.get('resource', {})
        if appt and appt.get('status') in ['booked', 'pending']:
            start_time = datetime.fromisoformat(appt['start'].replace('Z', '+00:00'))
            formatted_time = start_time.strftime("%A, %B %d at %I:%M %p")
            
            practitioner_name = "Unknown Provider"
            for participant in appt.get('participant', []):
                if participant.get('actor', {}).get('resourceType') == 'Practitioner':
                    practitioner = fhir_client.read("Practitioner", participant['actor']['reference'].split('/')[-1])
                    if practitioner:
                        practitioner_name = f"Dr. {get_resource_name(practitioner)}"
                    break
            
            appt_str = f"- {formatted_time} with {practitioner_name}"
            if appt.get('description'):
                appt_str += f" ({appt['description']})"
            
            formatted.append(appt_str)
    
    return "\n".join(formatted) if formatted else "No appointments found"
# chatbot/views/utils/formatters.py

def format_message(message, **kwargs):
    """Format messages with given parameters"""
    try:
        if isinstance(message, list):
            return '\n'.join(message)
        return str(message)
    except Exception as e:
        return str(message)
def send_message(message, user_id):
    """Sends a message and retrieves the response from the chat view."""
    try:
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.post(
            '/chat',
            data=json.dumps({'message': message, 'user_id': user_id}),
            content_type='application/json'
        )

        view_func = resolve('/chat').func
        response = view_func(request)
        
        response_data = json.loads(response.content)
        return response_data.get('messages', ["No response received."])[0]
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        return "Sorry, I couldn't process that message."