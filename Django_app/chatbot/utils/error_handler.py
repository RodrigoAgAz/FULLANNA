"""
Comprehensive Error Handler for ANNA
Provides standardized error handling and user-friendly responses
"""

import logging
import traceback
from typing import Dict, Any, Optional, Union
from django.http import JsonResponse
from .audit_logger import audit_logger

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling for ANNA"""
    
    @staticmethod
    async def handle_error(
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        request_path: Optional[str] = None
    ) -> JsonResponse:
        """Handle errors with appropriate responses and logging"""
        
        # Log the full error details
        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "request_path": request_path,
            "traceback": traceback.format_exc()
        }
        
        logger.error(
            f"Error occurred: {str(error)}",
            exc_info=True,
            extra={
                "user_id": user_id,
                "context": context,
                "request_path": request_path
            }
        )
        
        # Log to audit system
        if user_id:
            await audit_logger.log_error(
                user_id=user_id,
                error_type=type(error).__name__,
                error_message=str(error),
                details={"context": context, "request_path": request_path}
            )
        
        # Determine error type and response
        if isinstance(error, ConnectionError):
            return ErrorHandler._connection_error_response()
        elif isinstance(error, TimeoutError):
            return ErrorHandler._timeout_error_response()
        elif "FHIR" in str(error) or "fhir" in str(error).lower():
            return ErrorHandler._fhir_error_response()
        elif "OpenAI" in str(error) or "openai" in str(error).lower():
            return ErrorHandler._ai_error_response()
        elif "Twilio" in str(error) or "twilio" in str(error).lower():
            return ErrorHandler._notification_error_response()
        elif isinstance(error, PermissionError):
            return ErrorHandler._permission_error_response()
        elif isinstance(error, ValueError):
            return ErrorHandler._validation_error_response(str(error))
        else:
            return ErrorHandler._generic_error_response()
    
    @staticmethod
    def _connection_error_response() -> JsonResponse:
        """Handle connection errors"""
        return JsonResponse({
            "messages": [
                "I'm having trouble connecting to our services right now.",
                "This might be a temporary network issue.",
                "Please try again in a moment, or contact support if the problem persists."
            ],
            "type": "connection_error",
            "success": False,
            "retry_suggested": True
        }, status=503)
    
    @staticmethod
    def _timeout_error_response() -> JsonResponse:
        """Handle timeout errors"""
        return JsonResponse({
            "messages": [
                "The request is taking longer than expected.",
                "This might be due to high system load.",
                "Please try again, and consider simplifying your request if the issue continues."
            ],
            "type": "timeout_error",
            "success": False,
            "retry_suggested": True
        }, status=504)
    
    @staticmethod
    def _fhir_error_response() -> JsonResponse:
        """Handle FHIR service errors"""
        return JsonResponse({
            "messages": [
                "I'm having trouble accessing your medical records right now.",
                "This could be due to a temporary issue with our health data system.",
                "Please try again later or contact support if you need immediate access to your records."
            ],
            "type": "fhir_error",
            "success": False,
            "retry_suggested": True
        }, status=503)
    
    @staticmethod
    def _ai_error_response() -> JsonResponse:
        """Handle AI/OpenAI service errors"""
        return JsonResponse({
            "messages": [
                "I'm experiencing some difficulty processing your request right now.",
                "My AI systems might be temporarily unavailable.",
                "Please try rephrasing your question or try again in a few minutes."
            ],
            "type": "ai_error",
            "success": False,
            "retry_suggested": True
        }, status=503)
    
    @staticmethod
    def _notification_error_response() -> JsonResponse:
        """Handle notification service errors"""
        return JsonResponse({
            "messages": [
                "I'm unable to send notifications right now.",
                "Your request was processed, but you might not receive SMS or email notifications.",
                "Please check back later for any updates."
            ],
            "type": "notification_error",
            "success": False,
            "retry_suggested": False
        }, status=200)  # Still return 200 since main request might be successful
    
    @staticmethod
    def _permission_error_response() -> JsonResponse:
        """Handle permission errors"""
        return JsonResponse({
            "messages": [
                "You don't have permission to access this information.",
                "Please verify your identity or contact support for assistance.",
                "For your privacy and security, access to medical information is restricted."
            ],
            "type": "permission_error",
            "success": False,
            "retry_suggested": False
        }, status=403)
    
    @staticmethod
    def _validation_error_response(error_message: str) -> JsonResponse:
        """Handle validation errors"""
        # Clean up technical error messages for users
        user_message = ErrorHandler._clean_validation_message(error_message)
        
        return JsonResponse({
            "messages": [
                "There was an issue with the information provided:",
                user_message,
                "Please check your input and try again."
            ],
            "type": "validation_error",
            "success": False,
            "retry_suggested": True
        }, status=400)
    
    @staticmethod
    def _generic_error_response() -> JsonResponse:
        """Handle generic/unknown errors"""
        return JsonResponse({
            "messages": [
                "I apologize, but something unexpected happened.",
                "Our technical team has been notified of this issue.",
                "Please try again, or contact support if the problem continues."
            ],
            "type": "generic_error",
            "success": False,
            "retry_suggested": True
        }, status=500)
    
    @staticmethod
    def _clean_validation_message(message: str) -> str:
        """Clean up technical validation messages for user consumption"""
        # Common message replacements
        replacements = {
            "field": "information",
            "parameter": "value", 
            "null": "empty",
            "invalid": "incorrect",
            "required": "needed"
        }
        
        cleaned = message.lower()
        for tech_term, user_term in replacements.items():
            cleaned = cleaned.replace(tech_term, user_term)
        
        return cleaned.capitalize()
    
    @staticmethod
    async def handle_appointment_error(error: Exception, user_id: str = None) -> JsonResponse:
        """Handle appointment-specific errors"""
        await audit_logger.log_appointment(
            user_id=user_id or "unknown",
            action="error",
            details={"error": str(error)}
        )
        
        if "no slots available" in str(error).lower():
            return JsonResponse({
                "messages": [
                    "I couldn't find any available appointment slots for your requested time.",
                    "Would you like me to show you alternative times?",
                    "You can also call the office directly to check for cancellations."
                ],
                "type": "appointment_availability_error",
                "success": False,
                "booking_state": "slot_selection"
            })
        elif "provider not found" in str(error).lower():
            return JsonResponse({
                "messages": [
                    "I couldn't find the healthcare provider you're looking for.",
                    "Please check the spelling or try selecting from available providers.",
                    "Would you like me to show you a list of available providers?"
                ],
                "type": "appointment_provider_error",
                "success": False,
                "booking_state": "provider_selection"
            })
        else:
            return JsonResponse({
                "messages": [
                    "I encountered an issue while managing your appointment.",
                    "Please try again or contact the office directly.",
                    "Your request was not processed successfully."
                ],
                "type": "appointment_error",
                "success": False
            }, status=500)
    
    @staticmethod
    async def handle_medical_data_error(error: Exception, user_id: str = None) -> JsonResponse:
        """Handle medical data access errors"""
        await audit_logger.log_data_access(
            user_id=user_id or "unknown",
            resource_type="medical_data",
            resource_id="unknown",
            action="error"
        )
        
        return JsonResponse({
            "messages": [
                "I'm unable to access your medical information right now.",
                "This could be due to privacy settings or a temporary system issue.",
                "Please ensure you're properly authenticated and try again.",
                "Contact support if you continue to have trouble accessing your records."
            ],
            "type": "medical_data_error",
            "success": False
        }, status=503)

# Decorator for error handling
def handle_errors(func):
    """Decorator to handle errors in async functions"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Try to get user_id from args if it's a method with user_id
            user_id = None
            if args:
                if hasattr(args[0], 'user_id'):
                    user_id = args[0].user_id
                elif len(args) > 1 and isinstance(args[1], str) and '@' in args[1]:
                    user_id = args[1]
            
            return await ErrorHandler.handle_error(
                e, 
                user_id=user_id,
                context={"function": func.__name__}
            )
    
    return wrapper

# Convenience function
async def handle_error(error: Exception, **kwargs) -> JsonResponse:
    """Convenience function for error handling"""
    return await ErrorHandler.handle_error(error, **kwargs)