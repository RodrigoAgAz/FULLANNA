# project/utils/constants.py
from datetime import timedelta

# Business Hours and Time Settings
BUSINESS_HOURS_START = 9
BUSINESS_HOURS_END = 17
DEFAULT_TIMEZONE = "America/New_York"
MAX_FUTURE_BOOKING_DAYS = 90
SLOT_DURATION_MINUTES = 30
SCHEDULE_HORIZON_START = "2024-01-01T00:00:00Z"
SCHEDULE_HORIZON_END = "2050-12-31T23:59:59Z"

# Session Settings
SESSION_EXPIRY_SECONDS = 1800  # 30 minutes
SESSION_KEY_PREFIX = "session:"
SESSION_STORAGE_DAYS = 1  # Store sessions for 1 day

# Appointment Settings
APPOINTMENT_STATUS = {
    'BOOKED': 'booked',
    'PENDING': 'pending',
    'CANCELLED': 'cancelled',
    'COMPLETED': 'completed'
}

APPOINTMENT_TYPES = {
    '1': 'GP',
    '2': 'Nurse',
    '3': 'Specialist'
}

# FHIR Resource Types
RESOURCE_TYPES = {
    'PATIENT': 'Patient',
    'PRACTITIONER': 'Practitioner',
    'APPOINTMENT': 'Appointment',
    'SCHEDULE': 'Schedule',
    'SLOT': 'Slot',
    'CONDITION': 'Condition',
    'MEDICATION': 'MedicationStatement',
    'PROCEDURE': 'Procedure',
    'IMMUNIZATION': 'Immunization',
    'ALLERGY': 'AllergyIntolerance'
}

# Response Messages
MESSAGES = {
    'NO_APPOINTMENTS': "You don't have any upcoming appointments scheduled.",
    'BOOKING_CANCELLED': "Booking cancelled. Is there anything else I can help you with?",
    'VERIFY_IDENTITY': "Please verify your identity first by providing your email address.",
    'INVALID_EMAIL': "I couldn't find your record. Please verify your email address.",
    'SESSION_ERROR': "There was an error with your session. Please try again.",
    'BOOKING_ERROR': "There was an error with your booking. Please try again.",
    'WEEKEND_ERROR': "We are closed on weekends. Please select a weekday.",
    'HOURS_ERROR': "Our hours are 9 AM to 5 PM. Please select a time during business hours.",
    'PAST_DATE_ERROR': "Please select a future date and time.",
    'DATETIME_FORMAT_ERROR': """Could not understand the date/time format. Please try:
        - 'tomorrow at 2pm'
        - 'October 31st at 2pm'
        - 'next Tuesday at 2pm'"""
}

# Search Parameters
SEARCH_ATTEMPTS = [
    {'telecom': "email|{email}"},
    {'email': "{email}"},
    {'telecom': "{email}"},
    {'telecom:contains': "{email}"},
    {'telecom:exact': "email|{email}"}
]

# Intent Detection Settings
INTENT_CONFIDENCE_THRESHOLD = 0.7
MAX_TOKENS = 500
TEMPERATURE = 0

# Logging Settings
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'DEBUG'

# API Settings
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_RETRIES = 3
OPENAI_TIMEOUT = 30

# Default Mock Patient Data (for testing)
DEFAULT_MOCK_PATIENT = {
    "extension": [
        {
            "url": "http://example.org/fhir/StructureDefinition/height",
            "valueQuantity": {
                "value": 170,
                "unit": "cm"
            }
        },
        {
            "url": "http://example.org/fhir/StructureDefinition/weight",
            "valueQuantity": {
                "value": 70,
                "unit": "kg"
            }
        }
    ]
}