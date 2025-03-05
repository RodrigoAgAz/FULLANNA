# chatbot/views/services/symptom_guidance_service.py

import logging
from django.conf import settings
import json
from ..utils.formatters import format_message
from .fhir_service import FHIRService
import openai
from datetime import datetime
from asgiref.sync import sync_to_async
from openai import AsyncOpenAI
from ..utils.constants import OPENAI_MODEL

logger = logging.getLogger('chatbot')
class SymptomGuidanceService:
    def __init__(self):
        self.fhir_service = FHIRService()
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Define red flag symptoms
        self.RED_FLAGS = {
            'chest_pain': [
                'chest pain', 'chest tightness', 'crushing pain',
                'heart attack', 'cardiac', 'heart pain'
            ],
            'breathing': [
                'cannot breathe', 'difficulty breathing', 'shortness of breath',
                'struggling to breathe', 'gasping', 'choking'
            ],
            'stroke': [
                'face drooping', 'arm weakness', 'speech difficulty',
                'numbness one side', 'sudden confusion', 'sudden dizziness'
            ],
            'consciousness': [
                'unconscious', 'passed out', 'fainting',
                'not responding', 'lost consciousness'
            ],
            'bleeding': [
                'severe bleeding', 'heavy bleeding', 'uncontrolled bleeding',
                'bleeding heavily', 'blood loss'
            ],
            'allergic': [
                'anaphylaxis', 'allergic reaction', 'throat swelling',
                'cannot swallow', 'severe allergy'
            ]
        }
        
        # Risk levels with their descriptions
        self.RISK_LEVELS = {
            'EMERGENCY': {
                'level': 4,
                'action': 'CALL EMERGENCY SERVICES IMMEDIATELY (112 or 999)',
                'urgency': 'Immediate emergency attention required'
            },
            'HIGH': {
                'level': 3,
                'action': 'Seek immediate medical attention or go to the nearest urgent care center',
                'urgency': 'Urgent medical attention recommended'
            },
            'MEDIUM': {
                'level': 2,
                'action': 'Consider visiting urgent care or booking an urgent appointment',
                'urgency': 'Prompt medical attention advised'
            },
            'LOW': {
                'level': 1,
                'action': 'Schedule a routine appointment with your healthcare provider',
                'urgency': 'Non-urgent medical attention'
            }
        }

    async def red_flag_checker(self, symptom_description):
        """
        Check for red flag symptoms that require immediate emergency attention
        Returns: tuple (bool, list of matched red flags)
        """
        try:
            symptom_description = symptom_description.lower()
            matched_flags = []

            for category, phrases in self.RED_FLAGS.items():
                if any(phrase in symptom_description for phrase in phrases):
                    matched_flags.append(category)
                    await sync_to_async(logger.warning)(f"Red flag detected: {category} in symptom: {symptom_description}")

            return bool(matched_flags), matched_flags

        except Exception as e:
            await sync_to_async(logger.error)(f"Error in red flag checking: {str(e)}")
            return True, ['error_defaulting_to_emergency']  # Err on side of caution

    async def symptom_analyzer(self, symptom_description, patient_data=None):
        """
        Analyze symptoms using OpenAI for severity assessment
        Returns: dict with analysis results
        """
        try:
            prompt = await sync_to_async(self._build_analysis_prompt)(symptom_description, patient_data)
            
            response = await self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a medical triage assistant. Always err on the side of caution."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            analysis = json.loads(response.choices[0].message.content)
            await sync_to_async(logger.info)(f"Symptom analysis completed: {analysis}")
            return analysis

        except Exception as e:
            await sync_to_async(logger.error)(f"Error in symptom analysis: {str(e)}")
            return {
                'severity': 'HIGH',
                'confidence': 0.0,
                'recommendation': 'Due to analysis error, recommending careful evaluation',
                'error': str(e)
            }

    async def risk_level_determiner(self, symptom_analysis, red_flags=None):
        """
        Determine risk level based on symptom analysis and red flags
        Returns: dict with risk assessment
        """
        try:
            if red_flags:
                return {
                    'level': 'EMERGENCY',
                    'action': self.RISK_LEVELS['EMERGENCY']['action'],
                    'urgency': self.RISK_LEVELS['EMERGENCY']['urgency'],
                    'red_flags': red_flags,
                    'timestamp': datetime.utcnow().isoformat()
                }

            # Map severity to risk level
            severity_mapping = {
                'MILD': 'LOW',
                'MODERATE': 'MEDIUM',
                'SEVERE': 'HIGH',
                'CRITICAL': 'EMERGENCY'
            }

            assessed_level = severity_mapping.get(
                symptom_analysis.get('severity', 'SEVERE'),  # Default to SEVERE if unclear
                'HIGH'  # Default to HIGH if mapping fails
            )

            return {
                'level': assessed_level,
                'action': self.RISK_LEVELS[assessed_level]['action'],
                'urgency': self.RISK_LEVELS[assessed_level]['urgency'],
                'confidence': symptom_analysis.get('confidence', 0.0),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            await sync_to_async(logger.error)(f"Error in risk level determination: {str(e)}")
            return {
                'level': 'HIGH',
                'action': self.RISK_LEVELS['HIGH']['action'],
                'urgency': 'Due to assessment error, recommending urgent evaluation',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    async def response_formatter(self, risk_assessment, patient_data=None):
        """
        Format the response based on risk assessment
        Returns: dict with formatted response messages
        """
        try:
            # Standard disclaimer
            disclaimer = (
                "IMPORTANT: This is an automated guidance system and not a medical diagnosis. "
                "If you're unsure or your condition worsens, please seek immediate medical attention."
            )

            # Emergency message template
            if risk_assessment['level'] == 'EMERGENCY':
                messages = [
                    "🚨 EMERGENCY MEDICAL ATTENTION RECOMMENDED 🚨",
                    f"ACTION NEEDED: {risk_assessment['action']}",
                    "Key points:",
                    "- Call emergency services (112 or 999) immediately",
                    "- Do not delay seeking help",
                    "- Stay calm and find a safe location",
                    "",
                    disclaimer
                ]

            # High risk message template
            elif risk_assessment['level'] == 'HIGH':
                messages = [
                    "⚠️ URGENT MEDICAL ATTENTION ADVISED ⚠️",
                    f"RECOMMENDATION: {risk_assessment['action']}",
                    "Next steps:",
                    "- Visit your nearest urgent care center",
                    "- If symptoms worsen, call emergency services",
                    "- Keep someone informed of your condition",
                    "",
                    disclaimer
                ]

            # Medium risk message template
            elif risk_assessment['level'] == 'MEDIUM':
                messages = [
                    "🏥 MEDICAL ATTENTION RECOMMENDED",
                    f"RECOMMENDATION: {risk_assessment['action']}",
                    "Options:",
                    "- Visit an urgent care center",
                    "- Book an urgent appointment with your doctor",
                    "- Monitor your symptoms closely",
                    "",
                    disclaimer
                ]

            # Low risk message template
            else:
                messages = [
                    "ℹ️ MEDICAL GUIDANCE",
                    f"RECOMMENDATION: {risk_assessment['action']}",
                    "Suggested steps:",
                    "- Book a routine appointment",
                    "- Monitor your symptoms",
                    "- If condition worsens, seek urgent care",
                    "",
                    disclaimer
                ]

            # Add local emergency numbers if available
            if patient_data and 'address' in patient_data:
                country = patient_data['address'][0].get('country', 'Unknown')
                messages.append(f"\nLocal emergency numbers for {country}:")
                if country == "Italy":
                    messages.append("Emergency: 112")
                    messages.append("Medical Emergency: 118")
                elif country == "United Kingdom":
                    messages.append("Emergency: 999 or 112")
                    messages.append("NHS Non-emergency: 111")

            return {
                'messages': messages,
                'risk_level': risk_assessment['level'],
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            await sync_to_async(logger.error)(f"Error formatting response: {str(e)}")
            return {
                'messages': [
                    "⚠️ ERROR IN PROCESSING",
                    "For your safety, please seek medical attention or call emergency services if you're concerned.",
                    "",
                    disclaimer
                ],
                'risk_level': 'ERROR',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def _build_analysis_prompt(self, symptom_description, patient_data):
        """Helper method to build the analysis prompt"""
        base_prompt = f"""
        Analyze the following symptoms and provide a severity assessment.
        Symptoms: {symptom_description}
        
        Respond in the following JSON format:
        {{
            "severity": "MILD|MODERATE|SEVERE|CRITICAL",
            "confidence": <float 0-1>,
            "recommendation": <string>,
            "key_symptoms": [<list of key symptoms identified>],
            "reasoning": <string explaining assessment>
        }}
        
        Always err on the side of caution. If in doubt, rate severity higher.
        """

        if patient_data:
            # Add relevant patient information to the prompt
            age = None
            if 'birthDate' in patient_data:
                birth_date = datetime.strptime(patient_data['birthDate'], '%Y-%m-%d')
                age = (datetime.now() - birth_date).days // 365

            additional_context = f"""
            Patient Context:
            - Age: {age if age else 'Unknown'} years
            - Gender: {patient_data.get('gender', 'Unknown')}
            """
            base_prompt += additional_context

        return base_prompt

    async def provide_specific_info(self, user_query):
        """
        Provide detailed information addressing the user's specific query.
        Uses OpenAI to generate a structured and informative response.
        """
        try:
            prompt = f"""
            You are a medical information assistant. Provide a detailed, accurate, and easy-to-understand answer to the following question:

            "{user_query}"

            Structure your response with numbered points, covering the following aspects:
            1. Explanation of the condition: what it is, what causes it, how it's transmitted, etc.
            2. Common symptoms.
            3. Diagnostic methods.
            4. Treatment options.
            5. When to seek medical attention.

            Include a disclaimer at the end stating that this information is for educational purposes only and should not replace professional medical advice.
            """

            response = await openai.ChatCompletion.acreate(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful and accurate medical information assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            detailed_info = response.choices[0].message.content.strip()

            return {
                'messages': [detailed_info]
            }

        except Exception as e:
            await sync_to_async(logger.error)(f"Error in provide_specific_info: {str(e)}")
            return {
                'messages': ["I'm sorry, I couldn't retrieve detailed information at this time."]
            }
print ("41")