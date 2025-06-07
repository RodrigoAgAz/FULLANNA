"""
Test Fixtures for ANNA
Provides mock objects and test data for unit tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime
from typing import Dict, Any, List

@pytest.fixture
def mock_fhir_service():
    """Mock FHIR service for testing"""
    service = AsyncMock()
    
    # Mock patient data
    service.search.return_value = {
        'entry': [{
            'resource': {
                'resourceType': 'Patient',
                'id': 'test-patient-123',
                'name': [{'given': ['John'], 'family': 'Doe'}],
                'birthDate': '1990-01-01',
                'telecom': [
                    {'system': 'email', 'value': 'john.doe@example.com'},
                    {'system': 'phone', 'value': '+1-555-123-4567'}
                ]
            }
        }]
    }
    
    service.get_patient_by_email.return_value = {
        'id': 'test-patient-123',
        'resource': {
            'resourceType': 'Patient',
            'id': 'test-patient-123',
            'name': [{'given': ['John'], 'family': 'Doe'}],
            'birthDate': '1990-01-01'
        }
    }
    
    return service

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    client = AsyncMock()
    
    # Default response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"intent": "greeting", "confidence": 0.95, "entities": {}}'))
    ]
    
    client.chat.completions.create.return_value = mock_response
    return client

@pytest.fixture
def mock_openai_manager():
    """Mock OpenAI manager for testing"""
    manager = AsyncMock()
    
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='Test response from AI'))
    ]
    
    manager.chat_completion.return_value = mock_response
    manager.detect_intent_with_ai.return_value = {
        "intent": "greeting",
        "confidence": 0.95,
        "entities": {}
    }
    
    return manager

@pytest.fixture
def mock_session_data():
    """Mock session data for testing"""
    return {
        'id': 'test-session-123',
        'greeted': False,
        'booking_state': None,
        'verified': True,
        'last_interaction': datetime.now().isoformat(),
        'patient': {
            'id': 'test-patient-123',
            'resource': {
                'name': [{'given': ['John'], 'family': 'Doe'}],
                'birthDate': '1990-01-01'
            }
        },
        'conversation_history': [],
        'user_facts': {},
        'current_topic': {}
    }

@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing"""
    manager = AsyncMock()
    
    # Mock session data
    session_data = {
        'id': 'test-session-123',
        'greeted': False,
        'verified': True,
        'patient': None,
        'conversation_history': []
    }
    
    manager.get_session.return_value = session_data
    manager.update_session.return_value = None
    manager.save_session.return_value = True
    
    return manager

@pytest.fixture
def mock_notification_service():
    """Mock notification service for testing"""
    service = AsyncMock()
    
    service.send_sms.return_value = True
    service.send_appointment_reminder.return_value = True
    service.send_medication_reminder.return_value = True
    service.send_lab_results_notification.return_value = True
    service.send_emergency_alert.return_value = True
    
    return service

@pytest.fixture
def mock_email_service():
    """Mock email service for testing"""
    service = AsyncMock()
    
    service.send_verification_email.return_value = "123456"
    service.verify_code.return_value = True
    service.send_welcome_email.return_value = True
    service.send_password_reset_email.return_value = True
    
    return service

@pytest.fixture
def sample_patient_data():
    """Sample patient data for testing"""
    return {
        'id': 'test-patient-123',
        'resource': {
            'resourceType': 'Patient',
            'id': 'test-patient-123',
            'name': [{'given': ['John'], 'family': 'Doe'}],
            'birthDate': '1990-01-01',
            'gender': 'male',
            'telecom': [
                {'system': 'email', 'value': 'john.doe@example.com'},
                {'system': 'phone', 'value': '+1-555-123-4567'}
            ],
            'address': [{
                'line': ['123 Main St'],
                'city': 'Anytown',
                'state': 'NY',
                'postalCode': '12345'
            }]
        }
    }

@pytest.fixture
def sample_lab_results():
    """Sample lab results for testing"""
    return [
        {
            'test_name': 'Hemoglobin A1C',
            'value': '6.8%',
            'reference_range': '< 7.0%',
            'date': '2024-01-15',
            'status': 'final'
        },
        {
            'test_name': 'Total Cholesterol',
            'value': '180 mg/dL',
            'reference_range': '< 200 mg/dL',
            'date': '2024-01-15',
            'status': 'final'
        },
        {
            'test_name': 'Blood Pressure',
            'value': '128/82 mmHg',
            'reference_range': '< 130/80 mmHg',
            'date': '2024-01-15',
            'status': 'final'
        }
    ]

@pytest.fixture
def sample_appointments():
    """Sample appointment data for testing"""
    return [
        {
            'id': 'appt-001',
            'start': '2024-02-15T10:00:00Z',
            'end': '2024-02-15T10:30:00Z',
            'status': 'booked',
            'participant': [
                {
                    'actor': {
                        'reference': 'Practitioner/dr-smith',
                        'display': 'Dr. Sarah Smith'
                    }
                }
            ],
            'description': 'Annual Physical Exam'
        },
        {
            'id': 'appt-002',
            'start': '2024-03-01T14:00:00Z',
            'end': '2024-03-01T14:30:00Z',
            'status': 'booked',
            'participant': [
                {
                    'actor': {
                        'reference': 'Practitioner/dr-jones',
                        'display': 'Dr. Michael Jones'
                    }
                }
            ],
            'description': 'Follow-up Consultation'
        }
    ]

@pytest.fixture
def sample_medical_conditions():
    """Sample medical conditions for testing"""
    return [
        {
            'id': 'condition-001',
            'code': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'code': '44054006',
                    'display': 'Type 2 diabetes mellitus'
                }]
            },
            'clinicalStatus': {
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                    'code': 'active'
                }]
            },
            'recordedDate': '2023-06-15'
        },
        {
            'id': 'condition-002',
            'code': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'code': '38341003',
                    'display': 'Essential hypertension'
                }]
            },
            'clinicalStatus': {
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                    'code': 'active'
                }]
            },
            'recordedDate': '2023-08-22'
        }
    ]

@pytest.fixture
def sample_medications():
    """Sample medication data for testing"""
    return [
        {
            'id': 'med-001',
            'medicationCodeableConcept': {
                'coding': [{
                    'system': 'http://www.nlm.nih.gov/research/umls/rxnorm',
                    'code': '860975',
                    'display': 'Metformin 500 MG Oral Tablet'
                }]
            },
            'dosageInstruction': [{
                'text': 'Take one tablet twice daily with meals',
                'timing': {
                    'repeat': {
                        'frequency': 2,
                        'period': 1,
                        'periodUnit': 'd'
                    }
                }
            }],
            'status': 'active'
        },
        {
            'id': 'med-002',
            'medicationCodeableConcept': {
                'coding': [{
                    'system': 'http://www.nlm.nih.gov/research/umls/rxnorm',
                    'code': '316049',
                    'display': 'Lisinopril 10 MG Oral Tablet'
                }]
            },
            'dosageInstruction': [{
                'text': 'Take one tablet once daily',
                'timing': {
                    'repeat': {
                        'frequency': 1,
                        'period': 1,
                        'periodUnit': 'd'
                    }
                }
            }],
            'status': 'active'
        }
    ]

@pytest.fixture
def mock_context_manager():
    """Mock context manager for testing"""
    manager = Mock()
    
    manager.update_conversation_context.return_value = {
        'conversation_history': [],
        'current_topic': {'type': 'greeting', 'name': 'greeting'},
        'user_facts': {}
    }
    
    manager.get_context_summary.return_value = "General conversation"
    manager.reset_context.return_value = {'conversation_history': []}
    
    return manager

@pytest.fixture
def mock_audit_logger():
    """Mock audit logger for testing"""
    logger = AsyncMock()
    
    logger.log_event.return_value = None
    logger.log_login.return_value = None
    logger.log_data_access.return_value = None
    logger.log_conversation.return_value = None
    logger.log_appointment.return_value = None
    logger.log_medical_query.return_value = None
    logger.log_error.return_value = None
    logger.log_security_event.return_value = None
    
    return logger

@pytest.fixture
def mock_health_checker():
    """Mock health checker for testing"""
    checker = AsyncMock()
    
    checker.check_all_services.return_value = {
        'fhir': {'status': 'healthy', 'message': 'FHIR service is accessible'},
        'redis': {'status': 'healthy', 'message': 'Redis is accessible'},
        'openai': {'status': 'healthy', 'message': 'OpenAI API is accessible'},
        'medlineplus': {'status': 'healthy', 'message': 'MedlinePlus API accessible'},
        'twilio': {'status': 'degraded', 'message': 'Twilio not configured'},
        'email': {'status': 'healthy', 'message': 'Email service configured'},
        'summary': {
            'status': 'healthy',
            'total_services': 6,
            'healthy': 5,
            'degraded': 1,
            'unhealthy': 0
        }
    }
    
    checker.check_service.return_value = {
        'status': 'healthy',
        'message': 'Service is accessible'
    }
    
    return checker

# Test data constants
TEST_USER_EMAIL = "test.user@example.com"
TEST_USER_ID = "test-user-123"
TEST_SESSION_ID = "test-session-123"
TEST_PHONE_NUMBER = "+1-555-123-4567"
TEST_VERIFICATION_CODE = "123456"

# Common test messages
TEST_MESSAGES = {
    'greeting': "Hello",
    'appointment_request': "I want to book an appointment",
    'symptom_report': "I have a headache and fever",
    'lab_results_query': "What were my cholesterol results?",
    'medical_info_query': "What is diabetes?",
    'goodbye': "Thank you, goodbye"
}