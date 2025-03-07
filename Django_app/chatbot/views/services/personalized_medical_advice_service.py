#!/usr/bin/env python
"""
personalized_medical_advice_service.py

A production-ready, asynchronous module for generating personalized medical advice.
This service combines:
  - Patient-specific data from your FHIR server (via FHIRService from your codebase)
  - Recent conversation context (via your session/conversation manager)
  - Evidence-based guidelines from MedlinePlus Connect (queried via HTTP)
into a comprehensive prompt for GPT-4. The final advice always includes a prominent disclaimer.

Before deploying:
  - Ensure that your FHIR server (settings.FHIR_SERVER_URL) and credentials (from .env) are correct.
  - Verify that the MedlinePlus Connect query parameters match your requirements.
  - Confirm that your conversation manager functions are correctly integrated.
"""

import logging
import asyncio
from datetime import datetime
from typing import List, Dict
import requests
import xml.etree.ElementTree as ET
import openai

from django.conf import settings
from chatbot.views.services.fhir_service import FHIRService

# Configure logging
logger = logging.getLogger("PersonalizedMedicalAdvice")
logger.setLevel(logging.INFO)

# ------------------------------------------------------------------------------
# Evidence-Based Guidelines via MedlinePlus Connect
# ------------------------------------------------------------------------------
print ("29")
# Mapping from condition names to MedlinePlus Connect codes.
CONDITION_CODE_MAPPING = {
    # Standard conditions
    "diabetes": "44054006",      # SNOMED code for Type 2 diabetes
    "hypertension": "38341003",  # SNOMED code for hypertension
    
    # Pain conditions with SNOMED codes
    "back_pain": "161891005",    # SNOMED code for back pain
    "headache": "25064002",      # SNOMED code for headache
    "leg_pain": "90834002",      # SNOMED code for leg pain
    "chest_pain": "29857009",    # SNOMED code for chest pain
    "abdominal_pain": "21522001", # SNOMED code for abdominal pain
    "knee_pain": "30989003",     # SNOMED code for knee pain
    "arm_pain": "45326000",      # SNOMED code for arm pain
    "foot_pain": "47933007",     # SNOMED code for foot pain
    "hand_pain": "53057004"      # SNOMED code for hand pain
}

def get_medlineplus_guidelines(condition: str) -> str:
    """
    Query MedlinePlus Connect for guideline text for the given condition.
    Returns guideline text or None.
    """
    code = CONDITION_CODE_MAPPING.get(condition.lower())
    if not code:
        logger.warning(f"No mapping found for condition: {condition}")
        return None

    base_url = "https://connect.medlineplus.gov/service"
    params = {
        "mainSearchCriteria.v.c": code,
        "informationRecipient.language": "en"
    }
    try:
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            guideline_text = None
            for desc in root.iter('description'):
                if desc.text:
                    guideline_text = desc.text.strip()
                    break
            if guideline_text:
                logger.info(f"Retrieved guideline for {condition}")
                return guideline_text
            else:
                logger.warning(f"No description found for {condition}")
                return None
        else:
            logger.error(f"MedlinePlus error {response.status_code} for condition {condition}")
            return None
    except Exception as e:
        logger.error(f"Error querying MedlinePlus for {condition}: {e}")
        return None

def get_evidence_based_guidelines(conditions: List[str]) -> Dict[str, str]:
    """
    For each condition in the list, query MedlinePlus Connect and return a mapping.
    """
    guidelines = {}
    for cond in conditions:
        text = get_medlineplus_guidelines(cond)
        if text:
            guidelines[cond] = text
    return guidelines

# ------------------------------------------------------------------------------
# Asynchronous Summarization of Conversation Context
# ------------------------------------------------------------------------------
def redact_sensitive_info(text: str) -> str:
    """
    Stub for redacting sensitive information. Replace with real redaction as needed.
    """
    return text

async def summarize_messages(messages: List[str], openai_client: "AsyncGPT4Client") -> str:
    """
    Uses GPT-4-turbo to generate a concise bullet-point summary of conversation context.
    Redacts sensitive data before summarization.
    """
    if not messages:
        return ""
    joined_messages = "\n".join(f"User: {redact_sensitive_info(m)}" for m in messages)
    system_prompt = (
        "You are an assistant that summarizes conversation context. "
        "Return a concise bullet list (max ~100 tokens) capturing key user info "
        "(symptoms, conditions, preferences) without including any sensitive data."
    )
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Conversation so far:\n{joined_messages}"}
    ]
    try:
        response = await openai_client.chat_completions_create(
            model="gpt-4-turbo",
            messages=prompt_messages,
            temperature=0.7,
            max_tokens=150
        )
        summary_text = response.choices[0].message.content.strip()
        return summary_text
    except Exception as e:
        logger.error(f"Error summarizing messages: {e}", exc_info=True)
        return ""

# ------------------------------------------------------------------------------
# Asynchronous GPT-4 Client Using OpenAI's Async API
# ------------------------------------------------------------------------------
class AsyncGPT4Client:
    def __init__(self, api_key: str):
        self.api_key = api_key
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)

    async def chat_completions_create(self, model: str, messages: List[dict],
                                     temperature: float = 0.7,
                                     max_tokens: int = 300) -> dict:
        """
        Calls the OpenAI async ChatCompletion API.
        """
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response
        except Exception as e:
            logger.error(f"Error generating GPT-4 response: {e}")
            raise

    async def generate_advice(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat_completions_create(
            model="gpt-4o-mini",  # Using the more recent model
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()

# ------------------------------------------------------------------------------
# Conversation Context Retrieval (Replace with your real conversation/session management)
# ------------------------------------------------------------------------------
def get_conversation_context(patient_id: str) -> Dict[str, any]:
    """
    Retrieve recent conversation context for a patient.
    Replace this with your actual session/conversation manager call.
    """
    return {
        "recent_messages": [
            "I have been worried about my blood sugar levels.",
            "Last week I asked how to control my diabetes."
        ],
        "user_facts": {"diabetes": True}
    }

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# Symptom Analysis & Risk Assessment - Enhanced for ANNA Chatbot
# ------------------------------------------------------------------------------
class SymptomAnalyzer:
    """
    Handles all aspects of symptom analysis and risk assessment with
    properly implemented async methods.
    """
    def __init__(self, openai_client=None):
        """Initialize with optional OpenAI client"""
        from django.conf import settings
        from openai import AsyncOpenAI
        
        self.openai_client = openai_client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.fhir_service = FHIRService()
        
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
                    logging.warning(f"Red flag detected: {category} in symptom: {symptom_description}")

            return bool(matched_flags), matched_flags

        except Exception as e:
            logging.error(f"Error in red flag checking: {str(e)}")
            return True, ['error_defaulting_to_emergency']  # Err on side of caution

    async def symptom_analyzer(self, symptom_description, patient_data=None):
        """
        Analyze symptoms using OpenAI for severity assessment
        Returns: dict with analysis results
        """
        try:
            prompt = self._build_analysis_prompt(symptom_description, patient_data)
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a medical triage assistant. Always respond with a valid JSON object."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}  # Force JSON response format
            )

            analysis = response.choices[0].message.content
            try:
                import json
                analysis = json.loads(analysis)
                logging.info(f"Symptom analysis completed: {analysis}")
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing JSON response: {e}, content: {analysis}")
                # If the response can't be parsed as JSON, extract "severity" if possible
                if '"severity"' in analysis:
                    severity = "HIGH"  # Default
                    if '"severity":"MILD"' in analysis.replace(" ", ""):
                        severity = "MILD"
                    elif '"severity":"MODERATE"' in analysis.replace(" ", ""):
                        severity = "MODERATE"
                    elif '"severity":"SEVERE"' in analysis.replace(" ", ""):
                        severity = "SEVERE"
                    elif '"severity":"CRITICAL"' in analysis.replace(" ", ""):
                        severity = "CRITICAL"
                        
                    analysis = {
                        'severity': severity,
                        'confidence': 0.7,
                        'recommendation': 'Extracted from malformed JSON response',
                        'possible_causes': ['Unknown - JSON parsing error'],
                        'next_steps': ['Consult a healthcare professional']
                    }
                else:
                    # Default cautious response
                    analysis = {
                        'severity': 'HIGH',
                        'confidence': 0.5,
                        'recommendation': 'See a healthcare professional soon',
                        'possible_causes': ['Unable to analyze symptoms'],
                        'next_steps': ['Consult a healthcare professional']
                    }
                
            return analysis

        except Exception as e:
            logging.error(f"Error in symptom analysis: {str(e)}")
            return {
                'severity': 'HIGH',
                'confidence': 0.0,
                'recommendation': 'Due to analysis error, recommending careful evaluation',
                'error': str(e)
            }

    def _build_analysis_prompt(self, symptom_description, patient_data=None):
        """
        Build a prompt for the OpenAI API to analyze symptoms.
        """
        # Base prompt elements
        prompt_parts = [
            "MEDICAL SYMPTOM ASSESSMENT: Analyze the following symptoms in JSON format.\n",
            f"USER SYMPTOMS: {symptom_description}\n",
        ]
        
        # Add patient context if available
        if patient_data:
            age = None
            gender = None
            conditions = []
            
            if isinstance(patient_data, dict):
                # Extract age if birthDate is available
                if 'birthDate' in patient_data:
                    from datetime import datetime
                    try:
                        birth_date = datetime.strptime(patient_data['birthDate'], "%Y-%m-%d")
                        today = datetime.today()
                        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    except:
                        pass
                
                # Extract gender
                gender = patient_data.get('gender')
                
                # Try to extract conditions if they exist in the data
                if 'condition' in patient_data:
                    for condition in patient_data['condition']:
                        if isinstance(condition, dict) and 'code' in condition and 'text' in condition['code']:
                            conditions.append(condition['code']['text'])
            
            if age or gender or conditions:
                prompt_parts.append("PATIENT CONTEXT:")
                if age:
                    prompt_parts.append(f"- Age: {age}")
                if gender:
                    prompt_parts.append(f"- Gender: {gender}")
                if conditions:
                    prompt_parts.append(f"- Existing conditions: {', '.join(conditions)}")
                prompt_parts.append("\n")
        
        # Add response format instructions
        prompt_parts.append("""
RESPONSE FORMAT: Return a JSON object with the following keys:
{
    "severity": "MILD|MODERATE|SEVERE|CRITICAL",
    "confidence": <float between 0 and 1>,
    "recommendation": "<action recommendation>",
    "possible_causes": ["<cause1>", "<cause2>"],
    "next_steps": ["<step1>", "<step2>"]
}
        """)
        
        return "\n".join(prompt_parts)

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
            logging.error(f"Error in risk level determination: {str(e)}")
            return {
                'level': 'HIGH',  # Default to HIGH on error
                'action': self.RISK_LEVELS['HIGH']['action'],
                'urgency': self.RISK_LEVELS['HIGH']['urgency'],
                'error': str(e)
            }

    def response_formatter(self, risk_assessment, patient_data=None):
        """
        Format risk assessment into user-friendly messages
        Returns: dict with formatted messages
        """
        # Define disclaimer
        disclaimer = "This information is for educational purposes only and is not a substitute for professional medical advice. Always consult a healthcare professional."
        
        try:
            # Format messages based on risk level
            if risk_assessment['level'] == 'EMERGENCY':
                messages = [
                    "🚨 EMERGENCY: SEEK IMMEDIATE MEDICAL ATTENTION",
                    f"Urgency: {risk_assessment['urgency']}",
                    f"Action: {risk_assessment['action']}",
                    "",
                    disclaimer
                ]
            
            # High risk message template
            elif risk_assessment['level'] == 'HIGH':
                messages = [
                    "⚠️ URGENT MEDICAL ATTENTION RECOMMENDED",
                    f"Recommendation: {risk_assessment['action']}",
                    "Suggested steps:",
                    "- Get medical attention today",
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
            if patient_data and isinstance(patient_data, dict) and 'address' in patient_data:
                country = patient_data['address'][0].get('country', 'Unknown')
                messages.append(f"\nLocal emergency numbers for {country}:")
                if country == "Italy":
                    messages.append("Emergency: 112")
                    messages.append("Medical Emergency: 118")
                elif country == "United Kingdom":
                    messages.append("Emergency: 999")
                    messages.append("Non-emergency medical help: 111")
                elif country == "United States":
                    messages.append("Emergency: 911")
                else:
                    messages.append("Common Emergency Number: 112")
            
            return {"messages": messages}
            
        except Exception as e:
            logging.error(f"Error formatting response: {str(e)}")
            return {
                "messages": [
                    "⚠️ MEDICAL ATTENTION RECOMMENDED",
                    "I encountered an error analyzing your symptoms. Please consult a healthcare professional.",
                    disclaimer
                ]
            }

    async def provide_specific_info(self, symptom_description):
        """
        Provide specific information for the symptom using MedlinePlus guidelines
        when available, and fallback to predefined guidance when not.
        """
        # Extract location and type of pain
        location = None
        pain_words = ['ache', 'pain', 'hurt', 'sore', 'discomfort']
        
        # Simple location extraction
        body_parts = ['head', 'back', 'chest', 'stomach', 'leg', 'arm', 'foot', 'hand', 'knee']
        for part in body_parts:
            if part in symptom_description.lower():
                location = part
                break
        
        # Generic response
        if not location:
            return {"messages": []}
            
        # Map location to medical condition for MedlinePlus
        condition_mapping = {
            'back': 'back_pain',
            'head': 'headache',
            'leg': 'leg_pain',
            'chest': 'chest_pain',
            'stomach': 'abdominal_pain',
            'arm': 'arm_pain',
            'knee': 'knee_pain',
            'foot': 'foot_pain',
            'hand': 'hand_pain'
        }
        
        # Try to get MedlinePlus information if available
        medline_info = None
        if location in condition_mapping:
            # Add to CONDITION_CODE_MAPPING if not already there
            condition_name = condition_mapping[location]
            if condition_name in CONDITION_CODE_MAPPING:
                try:
                    medline_info = get_medlineplus_guidelines(condition_name)
                    logging.info(f"Retrieved MedlinePlus info for {condition_name}: {medline_info}")
                except Exception as e:
                    logging.error(f"Error getting MedlinePlus info for {condition_name}: {str(e)}")
        
        # If we got MedlinePlus info, use it
        if medline_info:
            messages = [
                f"Evidence-based guidelines for {location} pain:",
                medline_info
            ]
            return {"messages": messages}
        
        # Otherwise fall back to our predefined guidance
        messages = []
        
        if location == 'back':
            messages = [
                "For back pain:",
                "- Apply ice for the first 48-72 hours, then heat",
                "- Gentle stretching may help, but avoid strenuous activity",
                "- Over-the-counter pain relievers like ibuprofen may help reduce inflammation"
            ]
        elif location == 'head':
            messages = [
                "For headaches:",
                "- Rest in a quiet, dark room",
                "- Stay hydrated",
                "- Try a cold compress on your forehead",
                "- Track your headaches to identify patterns and triggers"
            ]
        elif location == 'leg':
            messages = [
                "For leg pain:",
                "- Rest and elevate the leg when possible",
                "- Apply ice to reduce swelling",
                "- Gentle stretching may help with muscle discomfort",
                "- Avoid prolonged standing if it worsens the pain"
            ]
        else:
            messages = [
                f"For {location} pain:",
                "- Rest the affected area when possible",
                "- Apply ice to reduce swelling and inflammation",
                "- Over-the-counter pain relievers may help with discomfort",
                "- Consult your healthcare provider if pain persists or worsens"
            ]
            
        return {"messages": messages}

# Personalized Medical Advice Service (Hybrid Approach, Async)
# ------------------------------------------------------------------------------
class PersonalizedMedicalAdviceService:
    def __init__(self, gpt_client=None, openai_client=None):
        """Initialize with optional GPT client and/or OpenAI client"""
        from django.conf import settings
        from openai import AsyncOpenAI
        
        # Set up GPT client
        if gpt_client:
            self.gpt_client = gpt_client
        else:
            self.gpt_client = AsyncGPT4Client(api_key=settings.OPENAI_API_KEY)
        
        # Set up OpenAI client directly
        self.openai_client = openai_client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
        # Use your actual FHIRService from your codebase
        self.fhir_service = FHIRService()
        
        # Create symptom analyzer and pass the OpenAI client
        self.symptom_analyzer = SymptomAnalyzer(openai_client=self.openai_client)

    async def get_personalized_advice(self, patient_id: str, user_query: str) -> str:
        """
        Combines patient data, conversation context, and evidence-based guidelines
        into a prompt for GPT-4, and returns personalized medical advice.
        """
        # Retrieve patient data via your FHIRService (using your real FHIR query)
        patient_resource = await asyncio.to_thread(self.fhir_service.get_patient, patient_id)
        if not patient_resource:
            return "Error: Patient data not found."

        patient_data = self._extract_patient_data(patient_resource)
        context = get_conversation_context(patient_id)
        recent_msgs = context.get("recent_messages", [])
        context_summary = await summarize_messages(recent_msgs, self.gpt_client)

        conditions = patient_data.get("conditions", [])
        guidelines = get_evidence_based_guidelines(conditions)

        prompt = self._build_prompt(user_query, patient_data, context_summary, guidelines)
        logger.info("Constructed prompt for GPT-4:")
        logger.info(prompt)

        advice = await self.gpt_client.generate_advice(prompt)
        advice = self._ensure_disclaimer(advice)
        return advice
        
    async def handle_symptom_query(self, message, patient_data=None):
        """
        Main method to handle symptom queries - providing personalized medical advice
        using GPT rather than template-based responses
        
        Args:
            message: The user's symptom description
            patient_data: Patient data from FHIR (optional)
            
        Returns:
            Dict with personalized advice messages
        """
        try:
            # Use GPT to provide personalized medical advice
            name = "there"
            age = "unknown"
            gender = "unknown"
            
            # Extract basic patient info if available
            if patient_data:
                if isinstance(patient_data, dict):
                    # Try to get name
                    if 'name' in patient_data and isinstance(patient_data['name'], list) and patient_data['name']:
                        given_name = patient_data['name'][0].get('given', [''])[0] if patient_data['name'][0].get('given') else ''
                        name = given_name or "there"
                        
                    # Try to get age
                    if 'birthDate' in patient_data:
                        from datetime import datetime
                        try:
                            birth_date = datetime.strptime(patient_data['birthDate'], "%Y-%m-%d")
                            today = datetime.today()
                            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                        except:
                            age = "unknown"
                            
                    # Get gender
                    gender = patient_data.get('gender', 'unknown')
            
            # Build a prompt for personalized medical advice - only include data that came from FHIR
            patient_info = []
            if name != "there":
                patient_info.append(f"Name: {name}")
            if age != "unknown" and age:
                patient_info.append(f"Age: {age}")
            if gender != "unknown" and gender:
                patient_info.append(f"Gender: {gender}")
            
            # Format patient info string or use generic greeting if no data available
            patient_line = f"Patient: {', '.join(patient_info)}" if patient_info else "Patient"
            
            prompt = f"""As a helpful medical advisor, provide personalized advice for this person:

{patient_line}
Symptom query: "{message}"

Please provide:
1. A brief, empathetic explanation of what might be happening
2. 3-5 practical steps they can take right now to address their symptoms
3. When they should see a doctor

Keep your advice natural and conversational, as if speaking directly to the person. 
Be practical and specific, but don't sound like a generic medical template.
IMPORTANT: End with a clear disclaimer about this being educational not professional medical advice.
"""

            # Get personalized advice from GPT
            from openai import AsyncOpenAI
            from django.conf import settings
            
            # Use symptom_analyzer's client if available, or create a new one
            if hasattr(self, 'symptom_analyzer') and hasattr(self.symptom_analyzer, 'openai_client'):
                client = self.symptom_analyzer.openai_client
            elif hasattr(self, 'gpt_client'):
                client = self.gpt_client
            else:
                # Create a new client as fallback
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful medical advisor providing personalized advice."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7  # Higher temperature for more natural language
            )
            
            advice = response.choices[0].message.content.strip()
            
            # Split into paragraphs for better message formatting
            advice_paragraphs = [p.strip() for p in advice.split('\n') if p.strip()]
            
            # Add disclaimer if not already present
            disclaimer = "This information is for educational purposes only and is not a substitute for professional medical advice."
            if not any(disclaimer.lower() in p.lower() for p in advice_paragraphs):
                advice_paragraphs.append(disclaimer)
            
            return {"messages": advice_paragraphs}
            
        except Exception as e:
            logging.error(f"Error generating personalized advice: {str(e)}")
            return {
                "messages": [
                    "I apologize, but I encountered an error processing your symptoms.",
                    "For any concerning symptoms, it's best to consult with a healthcare professional.",
                    "This information is for educational purposes only and is not a substitute for professional medical advice."
                ]
            }

    def _extract_patient_data(self, patient_resource: dict) -> dict:
        """
        Extracts relevant patient data from the FHIR Patient resource.
        Adjust extraction logic according to your actual FHIR resource structure.
        """
        data = {}
        birth_date_str = getattr(patient_resource, "birthDate", None)
        data["age"] = self._calculate_age(birth_date_str) if birth_date_str else "Unknown"
        # Replace these with your actual extraction calls, e.g., using self.fhir_service.get_patient_conditions
        data["conditions"] = ["diabetes", "hypertension"]
        data["medications"] = ["Metformin", "Lisinopril"]
        return data

    def _calculate_age(self, birth_date_str: str) -> int:
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
            today = datetime.today().date()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except Exception as e:
            logger.error(f"Error calculating age from {birth_date_str}: {e}")
            return 0

    def _build_prompt(self, user_query: str, patient_data: dict,
                      context_summary: str, guidelines: dict) -> str:
        system_message = (
            "You are a clinically accurate medical assistant providing personalized advice based on evidence-based guidelines. "
            "Always include this disclaimer at the end: 'This information is for educational purposes only and is not a substitute for professional medical advice.'"
        )
        prompt_lines = [system_message, "\nPatient Data:"]
        for key, value in patient_data.items():
            prompt_lines.append(f"- {key}: {value}")
        prompt_lines.append("\nEvidence-Based Guidelines:")
        if guidelines:
            for condition, rec in guidelines.items():
                prompt_lines.append(f"- {condition}: {rec}")
        else:
            prompt_lines.append("- None available")
        prompt_lines.append("\nConversation Context Summary:")
        prompt_lines.append(context_summary if context_summary else "No significant context.")
        prompt_lines.append("\nUser Query:")
        prompt_lines.append(user_query)
        return "\n".join(prompt_lines)

    def _ensure_disclaimer(self, advice_text: str) -> str:
        disclaimer = "This information is for educational purposes only and is not a substitute for professional medical advice."
        if disclaimer.lower() not in advice_text.lower():
            advice_text += "\n\n" + disclaimer
        return advice_text

# ------------------------------------------------------------------------------
# Stand-Alone Async Script Entry Point for Testing
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    async def main():
        gpt_client = AsyncGPT4Client(api_key=settings.OPENAI_API_KEY)
        advice_service = PersonalizedMedicalAdviceService(gpt_client)
        example_patient_id = "12345"  # Replace with a valid patient ID from your FHIR server
        user_query = "How should I manage my diabetes effectively?"
        advice = await advice_service.get_personalized_advice(example_patient_id, user_query)
        print("Personalized Medical Advice:")
        print(advice)

    asyncio.run(main())
print ("30")