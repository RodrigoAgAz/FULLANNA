import unittest
import pytest
import json
import hmac
import hashlib
import base64
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, RequestFactory
from django.conf import settings
from chatbot.utils.log_filters import RedactPIIFilter
from chatbot.middleware.twilio_signature import TwilioSignatureMiddleware
import logging
import redis_lock
from chatbot.tasks import process_preventive_care_reminders, process_medication_reminders_task

class TestTwilioSignatureMiddleware(TestCase):
    """Test that the Twilio signature middleware correctly validates signatures"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TwilioSignatureMiddleware(get_response=lambda request: None)
        self.original_token = settings.TWILIO_AUTH_TOKEN
        # Use a test token for consistency
        settings.TWILIO_AUTH_TOKEN = "test_auth_token"
        
    def tearDown(self):
        # Restore the original token
        settings.TWILIO_AUTH_TOKEN = self.original_token
    
    def test_valid_signature(self):
        """Test that valid signatures are accepted"""
        # Create a request with a valid signature
        request = self.factory.post('/webhooks/sms/', {'Body': 'Test message'})
        url = request.build_absolute_uri()
        body = request.body.decode() or ''
        data = url + body
        
        # Generate a valid signature
        digest = hmac.new(b"test_auth_token", data.encode(), hashlib.sha1).digest()
        valid_signature = base64.b64encode(digest).decode()
        
        # Add the signature to the request
        request.META['HTTP_X_TWILIO_SIGNATURE'] = valid_signature
        
        # The middleware should accept this request
        with patch.object(self.middleware, 'get_response') as mock_get_response:
            mock_get_response.return_value = 'response'
            response = self.middleware(request)
            mock_get_response.assert_called_once()
            
        self.assertEqual(response, 'response')
    
    def test_invalid_signature(self):
        """Test that invalid signatures are rejected"""
        # Create a request with an invalid signature
        request = self.factory.post('/webhooks/sms/', {'Body': 'Test message'})
        request.META['HTTP_X_TWILIO_SIGNATURE'] = 'invalid_signature'
        
        # The middleware should reject this request and return a 403
        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content.decode(), 'Invalid Twilio signature')

class TestRedactPIIFilter(unittest.TestCase):
    """Test the RedactPIIFilter redacts sensitive information from logs"""
    
    def setUp(self):
        self.pii_filter = RedactPIIFilter()
        
    def test_redact_phone_numbers(self):
        """Test that phone numbers are redacted from log messages"""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg="Patient phone number is 1234567890",
            args=(),
            exc_info=None
        )
        
        self.pii_filter.filter(record)
        self.assertEqual(record.msg, "Patient phone number is [PHONE]")
        
    def test_redact_ssn(self):
        """Test that SSNs are redacted from log messages"""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg="SSN is 123-45-6789",
            args=(),
            exc_info=None
        )
        
        self.pii_filter.filter(record)
        self.assertEqual(record.msg, "SSN is [SSN]")
        
    def test_redact_args(self):
        """Test that args are also redacted"""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg="Email: %s",
            args=('patient@example.com',),
            exc_info=None
        )
        
        self.pii_filter.filter(record)
        self.assertEqual(record.args[0], '[EMAIL]')

class TestCeleryTaskLocking(unittest.TestCase):
    """Test that Celery tasks properly acquire Redis locks"""
    
    @patch('redis_lock.Lock')
    @patch('chatbot.tasks.redis_client')
    def test_preventive_care_task_acquires_lock(self, mock_redis_client, mock_lock):
        """Test that the preventive care task acquires a Redis lock"""
        # Set up a mock context manager
        mock_lock_instance = MagicMock()
        mock_lock.return_value = mock_lock_instance
        
        # Mock the internal functions to avoid actually running the task
        with patch('chatbot.tasks.get_fhir_client'), \
             patch('chatbot.tasks.PreventiveCareReminderService'), \
             patch('chatbot.tasks.log_event'):
            
            # Run the task
            process_preventive_care_reminders()
            
            # Verify the lock was acquired with correct parameters
            mock_lock.assert_called_once_with(
                mock_redis_client, 
                "task-process_preventive_care_reminders", 
                expire=300
            )
            # Verify the lock context manager was entered
            mock_lock_instance.__enter__.assert_called_once()
            mock_lock_instance.__exit__.assert_called_once()
    
    @patch('redis_lock.Lock')
    @patch('chatbot.tasks.redis_client')
    def test_medication_reminders_task_acquires_lock(self, mock_redis_client, mock_lock):
        """Test that the medication reminders task acquires a Redis lock"""
        # Set up a mock context manager
        mock_lock_instance = MagicMock()
        mock_lock.return_value = mock_lock_instance
        
        # Mock the internal functions to avoid actually running the task
        with patch('chatbot.tasks.get_fhir_client'), \
             patch('chatbot.tasks.MedicationAdherenceReminderService'), \
             patch('chatbot.tasks.log_event'):
            
            # Run the task
            process_medication_reminders_task()
            
            # Verify the lock was acquired with correct parameters
            mock_lock.assert_called_once_with(
                mock_redis_client, 
                "task-process_medication_reminders", 
                expire=300
            )
            # Verify the lock context manager was entered
            mock_lock_instance.__enter__.assert_called_once()
            mock_lock_instance.__exit__.assert_called_once()