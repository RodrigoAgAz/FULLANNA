"""
Response Helper Utility for ANNA
Standardizes response formats across all handlers
"""

import logging
from typing import List, Dict, Any, Optional, Union
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class ResponseHelper:
    """Helper class for standardized response formatting"""
    
    @staticmethod
    def success_response(
        messages: Union[str, List[str]], 
        response_type: str = "success",
        metadata: Optional[Dict[str, Any]] = None
    ) -> JsonResponse:
        """Create a standardized success response"""
        if isinstance(messages, str):
            messages = [messages]
        
        response_data = {
            "messages": messages,
            "type": response_type,
            "success": True
        }
        
        if metadata:
            response_data.update(metadata)
        
        return JsonResponse(response_data)
    
    @staticmethod
    def error_response(
        message: str = "An error occurred",
        error_type: str = "general_error",
        status_code: int = 500
    ) -> JsonResponse:
        """Create a standardized error response"""
        response_data = {
            "messages": [message],
            "type": error_type,
            "success": False
        }
        
        return JsonResponse(response_data, status=status_code)
    
    @staticmethod
    def medical_info_response(
        title: str,
        content: List[str],
        disclaimer: bool = True
    ) -> JsonResponse:
        """Create a medical information response"""
        messages = []
        
        if title:
            messages.append(f"# {title}")
            messages.append("")  # Empty line for formatting
        
        messages.extend(content)
        
        if disclaimer:
            messages.extend([
                "",
                "⚠️ **Medical Disclaimer:** This information is for educational purposes only and does not replace professional medical advice. Always consult your healthcare provider for personalized medical guidance."
            ])
        
        return ResponseHelper.success_response(
            messages=messages,
            response_type="medical_info"
        )
    
    @staticmethod
    def appointment_response(
        messages: List[str],
        booking_state: Optional[str] = None,
        appointment_data: Optional[Dict] = None
    ) -> JsonResponse:
        """Create an appointment-related response"""
        metadata = {}
        
        if booking_state:
            metadata["booking_state"] = booking_state
        
        if appointment_data:
            metadata["appointment_data"] = appointment_data
        
        return ResponseHelper.success_response(
            messages=messages,
            response_type="appointment",
            metadata=metadata
        )
    
    @staticmethod
    def lab_results_response(
        title: str,
        results: List[Dict[str, Any]],
        summary: Optional[str] = None
    ) -> JsonResponse:
        """Create a lab results response"""
        messages = [f"# {title}"]
        
        if summary:
            messages.extend(["", summary, ""])
        
        for result in results:
            test_name = result.get('test_name', 'Unknown Test')
            value = result.get('value', 'N/A')
            reference_range = result.get('reference_range', '')
            date = result.get('date', '')
            
            messages.append(f"**{test_name}:** {value}")
            if reference_range:
                messages.append(f"  *Reference range: {reference_range}*")
            if date:
                messages.append(f"  *Date: {date}*")
            messages.append("")  # Space between results
        
        messages.append("💡 Discuss these results with your healthcare provider for proper interpretation.")
        
        return ResponseHelper.success_response(
            messages=messages,
            response_type="lab_results",
            metadata={"results_count": len(results)}
        )
    
    @staticmethod
    def symptom_guidance_response(
        severity: str,
        primary_symptoms: List[str],
        recommendations: List[str],
        emergency: bool = False
    ) -> JsonResponse:
        """Create a symptom guidance response"""
        severity_emojis = {
            'EMERGENCY': '🚨',
            'HIGH': '⚠️',
            'MODERATE': '⚕️',
            'LOW': 'ℹ️'
        }
        
        emoji = severity_emojis.get(severity, 'ℹ️')
        messages = [f"{emoji} **{severity} PRIORITY**"]
        
        if primary_symptoms:
            messages.extend([
                "",
                "**Symptoms identified:**",
                f"• {', '.join(primary_symptoms)}",
                ""
            ])
        
        if recommendations:
            messages.append("**Recommendations:**")
            for rec in recommendations:
                messages.append(f"• {rec}")
            messages.append("")
        
        if emergency:
            messages.extend([
                "🚨 **EMERGENCY NUMBERS:**",
                "• General Emergency: 112 (Europe), 911 (US)",
                "• If in doubt, call emergency services immediately!",
                ""
            ])
        
        messages.append("⚠️ This is not a substitute for professional medical evaluation.")
        
        return ResponseHelper.success_response(
            messages=messages,
            response_type="symptom_guidance",
            metadata={
                "severity": severity,
                "emergency": emergency,
                "symptom_count": len(primary_symptoms)
            }
        )
    
    @staticmethod
    def greeting_response(
        patient_name: Optional[str] = None,
        has_patient_data: bool = False
    ) -> JsonResponse:
        """Create a greeting response"""
        if patient_name:
            greeting = f"Hello, {patient_name}! 👋"
        else:
            greeting = "Hello! 👋"
        
        messages = [
            greeting,
            "",
            "I'm ANNA, your AI health assistant. I can help you with:",
            "",
            "🔹 **Medical Information** - Get information about conditions, treatments, and procedures",
            "🔹 **Appointment Management** - Schedule, view, or manage your appointments", 
            "🔹 **Health Records** - Access your medical records and lab results",
            "🔹 **Symptom Guidance** - Get guidance on symptoms and when to seek care",
            "",
            "How can I assist you today?"
        ]
        
        return ResponseHelper.success_response(
            messages=messages,
            response_type="greeting",
            metadata={
                "has_patient_data": has_patient_data,
                "patient_authenticated": bool(patient_name)
            }
        )
    
    @staticmethod
    def capabilities_response() -> JsonResponse:
        """Create a capabilities response"""
        messages = [
            "# What I Can Help You With",
            "",
            "## 🏥 **Medical Information**",
            "• Explain medical conditions, procedures, and treatments",
            "• Provide general health education",
            "• Answer questions about medications and their effects",
            "",
            "## 📅 **Appointment Management**", 
            "• Schedule new appointments with your healthcare providers",
            "• View your upcoming appointments",
            "• Help reschedule or cancel appointments",
            "",
            "## 📋 **Health Records Access**",
            "• View your medical history and conditions",
            "• Access lab results and test reports", 
            "• Review medication lists and allergies",
            "",
            "## 🩺 **Symptom Guidance**",
            "• Assess symptoms and provide guidance on urgency",
            "• Help determine when to seek medical care",
            "• Provide first aid and self-care recommendations",
            "",
            "## 🌐 **Multilingual Support**",
            "• Communicate in English and Spanish",
            "• Translate medical information when needed",
            "",
            "**Note:** I provide information and guidance but do not replace professional medical advice. Always consult your healthcare provider for personalized medical care."
        ]
        
        return ResponseHelper.success_response(
            messages=messages,
            response_type="capabilities"
        )

# Global instance for easy access
response_helper = ResponseHelper()

# Convenience functions for backward compatibility
def success_response(messages, response_type="success", metadata=None):
    return response_helper.success_response(messages, response_type, metadata)

def error_response(message="An error occurred", error_type="general_error", status_code=500):
    return response_helper.error_response(message, error_type, status_code)

def medical_info_response(title, content, disclaimer=True):
    return response_helper.medical_info_response(title, content, disclaimer)

def appointment_response(messages, booking_state=None, appointment_data=None):
    return response_helper.appointment_response(messages, booking_state, appointment_data)

def lab_results_response(title, results, summary=None):
    return response_helper.lab_results_response(title, results, summary)

def symptom_guidance_response(severity, primary_symptoms, recommendations, emergency=False):
    return response_helper.symptom_guidance_response(severity, primary_symptoms, recommendations, emergency)

def greeting_response(patient_name=None, has_patient_data=False):
    return response_helper.greeting_response(patient_name, has_patient_data)

def capabilities_response():
    return response_helper.capabilities_response()