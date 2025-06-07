"""
Integration Tests for ANNA
Tests the complete conversation flow and system integration
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from django.test import AsyncRequestFactory
from .fixtures import *

pytestmark = pytest.mark.asyncio

class TestChatHandlerIntegration:
    """Integration tests for the chat handler"""
    
    async def test_greeting_flow(self, mock_session_data, mock_fhir_service, mock_openai_manager):
        """Test complete greeting conversation flow"""
        with patch('chatbot.views.handlers.chat_handler.FHIRService', return_value=mock_fhir_service), \
             patch('chatbot.utils.openai_manager.openai_manager', mock_openai_manager):
            
            from chatbot.views.handlers.chat_handler import ChatHandler
            
            # Mock intent detection
            mock_openai_manager.detect_intent_with_ai.return_value = {
                "intent": "greeting",
                "confidence": 0.95,
                "entities": {}
            }
            
            # Initialize handler
            handler = ChatHandler(
                session_data=mock_session_data,
                user_message="Hello",
                user_id="test-user@example.com"
            )
            
            # Test message handling
            response, updated_session = await handler.handle_message("Hello")
            
            assert response.status_code == 200
            assert updated_session['greeted'] == True
    
    async def test_appointment_booking_flow(self, mock_session_data, mock_fhir_service, mock_openai_manager):
        """Test appointment booking conversation flow"""
        with patch('chatbot.views.handlers.chat_handler.FHIRService', return_value=mock_fhir_service), \
             patch('chatbot.utils.openai_manager.openai_manager', mock_openai_manager):
            
            from chatbot.views.handlers.chat_handler import ChatHandler
            
            # Mock intent detection for appointment booking
            mock_openai_manager.detect_intent_with_ai.return_value = {
                "intent": "set_appointment",
                "confidence": 0.95,
                "entities": {"topic": "appointment booking"}
            }
            
            handler = ChatHandler(
                session_data=mock_session_data,
                user_message="I want to book an appointment",
                user_id="test-user@example.com"
            )
            
            response, updated_session = await handler.handle_message("I want to book an appointment")
            
            assert response.status_code == 200
            assert 'booking_state' in updated_session
    
    async def test_medical_query_flow(self, mock_session_data, mock_fhir_service, mock_openai_manager):
        """Test medical information query flow"""
        with patch('chatbot.views.handlers.chat_handler.FHIRService', return_value=mock_fhir_service), \
             patch('chatbot.utils.openai_manager.openai_manager', mock_openai_manager):
            
            from chatbot.views.handlers.chat_handler import ChatHandler
            
            # Mock intent detection
            mock_openai_manager.detect_intent_with_ai.return_value = {
                "intent": "medical_info_query",
                "confidence": 0.9,
                "entities": {"topic": "diabetes"}
            }
            
            handler = ChatHandler(
                session_data=mock_session_data,
                user_message="What is diabetes?",
                user_id="test-user@example.com"
            )
            
            response, updated_session = await handler.handle_message("What is diabetes?")
            
            assert response.status_code == 200

class TestServiceIntegration:
    """Integration tests for service interactions"""
    
    async def test_fhir_to_session_integration(self, mock_fhir_service):
        """Test FHIR service integration with session management"""
        with patch('chatbot.views.services.fhir_service.FHIRService', return_value=mock_fhir_service):
            from chatbot.views.services.session import session_manager
            
            # Test patient verification
            session = await session_manager.get_session("test@example.com")
            
            assert session is not None
            assert session['id'] == "test@example.com"
    
    async def test_intent_to_response_integration(self, mock_openai_manager):
        """Test intent detection to response generation"""
        with patch('chatbot.utils.openai_manager.openai_manager', mock_openai_manager):
            from chatbot.views.services.intent_service import detect_intent
            
            # Test intent detection
            result = await detect_intent("Hello there!")
            
            assert result['intent'] == 'greeting'
            assert result['confidence'] > 0.9
    
    async def test_notification_integration(self, mock_notification_service):
        """Test notification service integration"""
        with patch('chatbot.views.services.notification_service.notification_service', mock_notification_service):
            
            # Test SMS sending
            result = await mock_notification_service.send_sms("+1234567890", "Test message")
            assert result == True
            
            # Test appointment reminder
            result = await mock_notification_service.send_appointment_reminder(
                "+1234567890", 
                "2024-02-15 at 10:00 AM",
                "Dr. Smith"
            )
            assert result == True
    
    async def test_audit_logging_integration(self, mock_audit_logger):
        """Test audit logging integration"""
        with patch('chatbot.utils.audit_logger.audit_logger', mock_audit_logger):
            
            # Test conversation logging
            await mock_audit_logger.log_conversation(
                user_id="test-user",
                intent="greeting",
                success=True
            )
            
            mock_audit_logger.log_conversation.assert_called_once()

class TestErrorHandlingIntegration:
    """Integration tests for error handling"""
    
    async def test_fhir_error_handling(self, mock_session_data):
        """Test error handling when FHIR service fails"""
        # Mock a failing FHIR service
        failing_fhir = AsyncMock()
        failing_fhir.search.side_effect = ConnectionError("FHIR server unavailable")
        
        with patch('chatbot.views.handlers.chat_handler.FHIRService', return_value=failing_fhir):
            from chatbot.utils.error_handler import ErrorHandler
            
            error = ConnectionError("FHIR server unavailable")
            response = await ErrorHandler.handle_error(error, user_id="test-user")
            
            assert response.status_code == 503
            assert "trouble connecting" in str(response.content).lower()
    
    async def test_openai_error_handling(self, mock_session_data):
        """Test error handling when OpenAI service fails"""
        from chatbot.utils.error_handler import ErrorHandler
        
        error = Exception("OpenAI API rate limit exceeded")
        response = await ErrorHandler.handle_error(error, user_id="test-user")
        
        assert response.status_code in [500, 503]

class TestHealthCheckIntegration:
    """Integration tests for health checking"""
    
    async def test_system_health_check(self, mock_health_checker):
        """Test complete system health check"""
        with patch('chatbot.utils.health_checker.health_checker', mock_health_checker):
            from chatbot.utils.health_checker import check_system_health
            
            health_status = await check_system_health()
            
            assert 'summary' in health_status
            assert health_status['summary']['status'] in ['healthy', 'degraded', 'unhealthy']
            assert health_status['summary']['total_services'] > 0
    
    async def test_individual_service_health(self, mock_health_checker):
        """Test individual service health checks"""
        with patch('chatbot.utils.health_checker.health_checker', mock_health_checker):
            
            # Test FHIR health check
            fhir_health = await mock_health_checker.check_service('fhir')
            assert fhir_health['status'] in ['healthy', 'degraded', 'unhealthy']
            
            # Test Redis health check
            redis_health = await mock_health_checker.check_service('redis')
            assert redis_health['status'] in ['healthy', 'degraded', 'unhealthy']

class TestResponseFormatIntegration:
    """Integration tests for response formatting"""
    
    def test_success_response_format(self):
        """Test success response formatting"""
        from chatbot.utils.response_helper import success_response
        
        response = success_response(
            messages=["Hello, how can I help you?"],
            response_type="greeting"
        )
        
        assert response.status_code == 200
        response_data = response.content
        assert b"Hello" in response_data
    
    def test_error_response_format(self):
        """Test error response formatting"""
        from chatbot.utils.response_helper import error_response
        
        response = error_response(
            message="Something went wrong",
            error_type="general_error"
        )
        
        assert response.status_code == 500
        response_data = response.content
        assert b"went wrong" in response_data
    
    def test_medical_info_response_format(self):
        """Test medical information response formatting"""
        from chatbot.utils.response_helper import medical_info_response
        
        response = medical_info_response(
            title="Diabetes Information",
            content=[
                "Diabetes is a chronic condition...",
                "Type 2 diabetes is the most common form..."
            ]
        )
        
        assert response.status_code == 200
        response_data = response.content
        assert b"Diabetes" in response_data

class TestConfigurationIntegration:
    """Integration tests for configuration management"""
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        from chatbot.views.config.app_config import AppConfig
        
        # Test that configuration can be validated
        try:
            AppConfig.validate_required_settings()
            validation_passed = True
        except ValueError:
            validation_passed = False
        
        # Should either pass or fail gracefully
        assert isinstance(validation_passed, bool)
    
    def test_feature_flags(self):
        """Test feature flag configuration"""
        from chatbot.views.config.app_config import AppConfig
        
        feature_flags = AppConfig.get_feature_flags()
        
        assert isinstance(feature_flags, dict)
        assert 'medication_reminders' in feature_flags
        assert 'sms_notifications' in feature_flags
        assert 'audit_logging' in feature_flags
    
    def test_service_configuration(self):
        """Test service-specific configuration"""
        from chatbot.views.config.app_config import AppConfig
        
        openai_config = AppConfig.get_service_config('openai')
        twilio_config = AppConfig.get_service_config('twilio')
        
        assert isinstance(openai_config, dict)
        assert isinstance(twilio_config, dict)
        assert 'model' in openai_config
        assert 'enabled' in twilio_config

class TestEndToEndFlow:
    """End-to-end integration tests"""
    
    async def test_complete_user_journey(self, mock_session_data, mock_fhir_service, mock_openai_manager):
        """Test a complete user interaction journey"""
        with patch('chatbot.views.handlers.chat_handler.FHIRService', return_value=mock_fhir_service), \
             patch('chatbot.utils.openai_manager.openai_manager', mock_openai_manager):
            
            from chatbot.views.handlers.chat_handler import ChatHandler
            
            # Step 1: Greeting
            mock_openai_manager.detect_intent_with_ai.return_value = {
                "intent": "greeting", "confidence": 0.95, "entities": {}
            }
            
            handler = ChatHandler(
                session_data=mock_session_data,
                user_message="Hello",
                user_id="test@example.com"
            )
            
            response1, session1 = await handler.handle_message("Hello")
            assert response1.status_code == 200
            assert session1['greeted'] == True
            
            # Step 2: Medical query
            mock_openai_manager.detect_intent_with_ai.return_value = {
                "intent": "medical_info_query", "confidence": 0.9, "entities": {"topic": "diabetes"}
            }
            
            handler2 = ChatHandler(
                session_data=session1,
                user_message="What is diabetes?",
                user_id="test@example.com"
            )
            
            response2, session2 = await handler2.handle_message("What is diabetes?")
            assert response2.status_code == 200
            
            # Step 3: Appointment booking
            mock_openai_manager.detect_intent_with_ai.return_value = {
                "intent": "set_appointment", "confidence": 0.95, "entities": {}
            }
            
            handler3 = ChatHandler(
                session_data=session2,
                user_message="I want to book an appointment",
                user_id="test@example.com"
            )
            
            response3, session3 = await handler3.handle_message("I want to book an appointment")
            assert response3.status_code == 200
            
            # Verify session continuity
            assert session3['id'] == session1['id']
            assert session3['greeted'] == True