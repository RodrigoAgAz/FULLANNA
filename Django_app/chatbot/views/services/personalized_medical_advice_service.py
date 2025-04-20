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
from typing import List, Dict, Any
import json
import openai

from django.conf import settings
from chatbot.views.services.fhir_service import FHIRService

# Configure logging
logger = logging.getLogger("PersonalizedMedicalAdvice")
logger.setLevel(logging.INFO)

# ------------------------------------------------------------------------------
# Evidence-Based Guidelines via MedlinePlus Connect
# ------------------------------------------------------------------------------
import logging
logger = logging.getLogger(__name__)
logger.debug("Personalized medical advice service module loaded")
# Mapping from condition names to MedlinePlus Connect codes.
CONDITION_CODE_MAPPING = {
    # Standard conditions
    "diabetes": "44054006",      # SNOMED code for Type 2 diabetes
    "hypertension": "38341003",  # SNOMED code for hypertension
    "insomnia": "248288008",     # SNOMED code for insomnia
    
    # Pain conditions with SNOMED codes
    "back_pain": "161891005",    # SNOMED code for back pain
    "headache": "25064002",      # SNOMED code for headache
    "leg_pain": "90834002",      # SNOMED code for leg pain
    "chest_pain": "29857009",    # SNOMED code for chest pain
    "abdominal_pain": "21522001", # SNOMED code for abdominal pain
    "knee_pain": "30989003",     # SNOMED code for knee pain
    "arm_pain": "45326000",      # SNOMED code for arm pain
    "foot_pain": "47933007",     # SNOMED code for foot pain
    "hand_pain": "53057004",     # SNOMED code for hand pain
    "ankle_pain": "16114001"     # SNOMED code for ankle pain
}

async def get_medlineplus_guidelines(condition: str) -> str:
    """
    Query MedlinePlus Connect for guideline text for the given condition.
    Returns guideline text or None.
    """
    # Find the condition in our mapping
    code = CONDITION_CODE_MAPPING.get(condition.lower())
    if not code:
        logger.warning(f"No mapping found for condition: {condition}")
        return None

    # Construct the MedlinePlus Connect API URL and parameters
    base_url = "https://connect.medlineplus.gov/service"
    params = {
        "mainSearchCriteria.v.c": code,
        "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.96",  # SNOMED CT
        "mainSearchCriteria.v.dn": condition.replace('_', ' '),
        "informationRecipient.language": "en",
        "knowledgeResponseType": "application/json"
    }
    
    logger.info(f"Making MedlinePlus API request for condition: {condition} with code: {code}")
    logger.info(f"Request URL: {base_url}")
    logger.info(f"Request parameters: {params}")
    
    try:
        # Use httpx for async HTTP requests
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Make the API request with proper error handling
            response = await client.get(base_url, params=params, timeout=10)
            logger.info(f"MedlinePlus API response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    # Parse the JSON response
                    logger.debug(f"MedlinePlus response content: {response.text[:500]}...")
                    
                    import json
                    response_data = json.loads(response.text)
                    guideline_text = None
                    
                    # Extract information from the JSON structure
                    # MedlinePlus Connect uses an Atom feed structure
                    if 'feed' in response_data and 'entry' in response_data['feed']:
                        entries = response_data['feed']['entry']
                        if entries and len(entries) > 0:
                            # Try to get the summary content first
                            if 'summary' in entries[0] and '_value' in entries[0]['summary']:
                                guideline_text = entries[0]['summary']['_value'].strip()
                                logger.info(f"Found summary element with text: {guideline_text[:100]}...")
                            
                            # If no summary, look for content or title
                            elif 'content' in entries[0] and '_value' in entries[0]['content']:
                                guideline_text = entries[0]['content']['_value'].strip()
                                logger.info(f"Found content element with text: {guideline_text[:100]}...")
                            
                            # Try title as last resort
                            elif 'title' in entries[0] and '_value' in entries[0]['title']:
                                guideline_text = entries[0]['title']['_value'].strip()
                                logger.info(f"Found title element with text: {guideline_text[:100]}...")
                    
                    if guideline_text:
                        logger.info(f"Successfully retrieved guideline for {condition}")
                        return guideline_text
                    else:
                        logger.warning(f"No useful information found for {condition} in JSON response")
                        return None
                except json.JSONDecodeError as json_error:
                    logger.error(f"JSON parsing error for MedlinePlus response: {json_error}")
                    logger.debug(f"Problematic JSON content: {response.text[:300]}...")
                    return None
            else:
                logger.error(f"MedlinePlus API error {response.status_code} for condition {condition}")
                logger.error(f"Error response: {response.text[:300]}...")
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
        
    def _extract_medical_topic(self, message):
        """
        Extract the main medical topic from a user message.
        """
        # List of common medical topics to check for
        medical_topics = {
            "diabetes": ["diabetes", "blood sugar", "glucose", "insulin"],
            "high blood pressure": ["high blood pressure", "hypertension", "blood pressure"],
            "cold vs flu": ["cold", "flu", "influenza", "difference between cold and flu"],
            "chest pain": ["chest pain", "heart attack", "angina"],
            "sprained ankle": ["sprain", "ankle", "sprained ankle", "twisted ankle"],
            "cholesterol": ["cholesterol", "ldl", "hdl", "lipids", "triglycerides"]
        }
        
        # Convert message to lowercase for case-insensitive matching
        message_lower = message.lower()
        
        # Check for topic matches
        for topic, keywords in medical_topics.items():
            if any(keyword in message_lower for keyword in keywords):
                return topic
                
        # No specific topic found
        return None

    async def handle_symptom_query(self, message, patient_data=None, topic=None, additional_data=None, conversation_context=None):
        """
        Main method to handle symptom queries - providing personalized medical advice
        using structured templates for common conditions and GPT for others
        
        Args:
            message: The user's symptom description
            patient_data: Patient data from FHIR (optional)
            topic: Specific medical topic to focus on (optional)
            additional_data: Any additional data like lab results, conditions etc. (optional)
            conversation_context: Context from previous conversations (optional)
            
        Returns:
            Dict with personalized advice messages
        """
        try:
            # Import our new modules (only import on demand to avoid circular imports)
            from chatbot.views.utils.response_formatter import format_symptom_response, format_medical_response
            from chatbot.views.utils.medical_info_templates import get_template_for_topic
            
            # Extract relevant patient info if available
            name = "there"
            age = None
            gender = None
            
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
                            pass  # Keep age as None if can't calculate
                            
                    # Get gender
                    if 'gender' in patient_data:
                        gender = patient_data['gender']
            
            # Check if we have additional data (FHIR resources like Condition or MedicationStatement)
            patient_conditions = []
            patient_allergies = []
            patient_medications = []
            relevant_history = []
            
            # Extract conditions, medications, and allergies from additional_data if available
            if additional_data:
                if isinstance(additional_data, dict):
                    # Check if it's a FHIR Bundle with entries
                    if 'resourceType' in additional_data and additional_data['resourceType'] == 'Bundle' and 'entry' in additional_data:
                        for entry in additional_data['entry']:
                            resource = entry.get('resource', {})
                            resource_type = resource.get('resourceType')
                            
                            # Extract conditions
                            if resource_type == 'Condition' and resource.get('clinicalStatus', {}).get('coding', [{}])[0].get('code') == 'active':
                                condition_name = resource.get('code', {}).get('text', 'Unknown condition')
                                patient_conditions.append(condition_name)
                                
                            # Extract medications
                            elif resource_type == 'MedicationStatement' and resource.get('status') == 'active':
                                med_name = resource.get('medicationCodeableConcept', {}).get('text', 'Unknown medication')
                                patient_medications.append(med_name)
                                
                            # Extract allergies
                            elif resource_type == 'AllergyIntolerance':
                                allergy_name = resource.get('code', {}).get('text', 'Unknown allergy')
                                patient_allergies.append(allergy_name)
            
            # Use provided topic or attempt to identify it from the message
            identified_topic = topic or await self._extract_symptom_keyphrase(message)
            template = get_template_for_topic(identified_topic) if identified_topic else None
            
            # Check for follow-up questions using context
            is_follow_up = False
            current_topic = None
            if conversation_context and conversation_context.get('user_facts'):
                # Check if we have a current_topic stored in user_facts
                current_topic = conversation_context.get('user_facts', {}).get('current_topic')
                
                # Check if this is a short message that might be a follow-up
                if len(message.split()) <= 8 and current_topic:
                    follow_up_indicators = [
                        "what", "why", "how", "should", "could", "when", "is it", "are there", 
                        "causes", "treated", "serious", "normal", "treatment", "cure", "heal",
                        "help", "manage", "deal with", "handle", "ease", "relieve", "mean"
                    ]
                    # Check if message contains follow-up indicators
                    if any(indicator in message.lower() for indicator in follow_up_indicators):
                        is_follow_up = True
                        # If we don't have a topic from the current message, use the current_topic
                        if not identified_topic and current_topic:
                            identified_topic = current_topic
                            template = get_template_for_topic(identified_topic) if identified_topic else None
                            logging.info(f"Follow-up detected, using previous topic: {current_topic}")
            
            # Check if this is an issue report - should be specifically routed to the new pathway
            is_issue_report = conversation_context and conversation_context.get('intent') == 'issue_report'
            
            # If we have a matching template, use it for a high-quality response
            if template and not is_issue_report:  # Skip template for issue reports to use our new pathway
                logging.info(f"Using template for topic: {identified_topic}")
                
                # Store the current topic in the response for context tracking
                # This will be helpful for follow-up questions
                if identified_topic:
                    if conversation_context and 'user_facts' in conversation_context:
                        conversation_context['user_facts']['current_topic'] = identified_topic
                        logging.info(f"Updated current_topic in user_facts: {identified_topic}")
                
                # Format using our new structured formatter
                if "variants" in template:
                    # This is a condition with variants (like cold vs flu)
                    from chatbot.views.utils.response_formatter import format_condition_variants
                    messages = format_condition_variants(
                        identified_topic, 
                        template["variants"]
                    )
                else:
                    # Standard medical info or symptom template
                    messages = format_medical_response(
                        question=message,
                        response_data=template,
                        include_brief_answer=True
                    )
                
                # For templates, also check if we need to add personalized warnings based on patient history
                if patient_conditions or patient_medications or patient_allergies:
                    # Try to determine if any conditions/meds/allergies are relevant to the current topic
                    relevant_history = await self._find_relevant_medical_history(
                        topic=identified_topic,
                        conditions=patient_conditions,
                        medications=patient_medications,
                        allergies=patient_allergies
                    )
                    
                    # If we found relevant history, include it at the top of the response
                    if relevant_history:
                        relevant_info = "⚠️ Note: "
                        if len(relevant_history) == 1:
                            relevant_info += f"You have a history of {relevant_history[0]}, which may affect management of {identified_topic}."
                        else:
                            conditions_list = ", ".join(relevant_history[:-1]) + " and " + relevant_history[-1]
                            relevant_info += f"You have a history of {conditions_list}, which may affect management of {identified_topic}."
                        
                        # Insert at the beginning of the messages
                        messages.insert(0, relevant_info)
                
                return {"messages": messages}
            
            # For issue reports or if no template, try to get MedlinePlus info or generate a response
            if is_issue_report or identified_topic:
                logging.info(f"Processing issue report for: {identified_topic or message}")
                
                # Extract the symptom keyphrase if we don't already have it
                if not identified_topic:
                    identified_topic = await self._extract_symptom_keyphrase(message)
                
                # If we have a keyphrase, try to get guidelines
                medlineplus_results = None
                if identified_topic:
                    try:
                        # First check if we can resolve a SNOMED code for the keyphrase
                        condition_code = await self.resolve_condition_code(identified_topic)
                        
                        if condition_code:
                            # Try to get MedlinePlus guidelines
                            medlineplus_results = await self._get_direct_medlineplus_info(identified_topic, condition_code)
                    except Exception as e:
                        logging.error(f"Error getting MedlinePlus info for {identified_topic}: {str(e)}")
                
                # Generate personalized response
                messages = []
                
                # Start with personalized warnings based on patient history if available
                if patient_conditions or patient_medications or patient_allergies:
                    relevant_history = await self._find_relevant_medical_history(
                        topic=identified_topic,
                        conditions=patient_conditions,
                        medications=patient_medications,
                        allergies=patient_allergies
                    )
                    
                    if relevant_history:
                        relevant_info = "⚠️ Note: "
                        if len(relevant_history) == 1:
                            relevant_info += f"You have a history of {relevant_history[0]}, which may affect management of {identified_topic}."
                        else:
                            conditions_list = ", ".join(relevant_history[:-1]) + " and " + relevant_history[-1]
                            relevant_info += f"You have a history of {conditions_list}, which may affect management of {identified_topic}."
                        
                        messages.append(relevant_info)
                        messages.append("")  # Add a blank line
                
                # Use MedlinePlus guidelines if available
                if medlineplus_results and 'messages' in medlineplus_results:
                    # Add the main MedlinePlus info
                    messages.extend(medlineplus_results['messages'])
                else:
                    # Use fallback generic guidance
                    messages.extend([
                        f"For {identified_topic or 'your symptoms'}:",
                        "- Rest and avoid exacerbating activities",
                        "- Apply ice or heat as appropriate",
                        "- Consider over-the-counter analgesics",
                        "- Consult your healthcare provider if symptoms persist beyond 3 days"
                    ])
                
                # Ensure we have the standard disclaimer at the end
                from chatbot.views.utils.response_formatter import STANDARD_DISCLAIMER
                if not any(STANDARD_DISCLAIMER.lower() in msg.lower() for msg in messages):
                    messages.append("")  # Add a blank line
                    messages.append(STANDARD_DISCLAIMER)
                
                # Update the session with the current topic
                if identified_topic and conversation_context and 'user_facts' in conversation_context:
                    conversation_context['user_facts']['current_topic'] = identified_topic
                
                return {"messages": messages, "extracted_topic": identified_topic}
            
            # Try the existing MedlinePlus info retrieval for backward compatibility
            try:
                logging.info(f"Attempting to retrieve specific MedlinePlus info for: {message}")
                
                # For follow-up questions, use the current topic if available
                lookup_message = message
                if is_follow_up and current_topic:
                    lookup_message = f"{current_topic} {message}"
                    logging.info(f"Enhanced lookup message for follow-up: {lookup_message}")
                
                specific_info = await self.provide_specific_info(lookup_message)
                if specific_info and specific_info.get("messages") and len(specific_info["messages"]) > 0:
                    # We have specific MedlinePlus info available, use it
                    logging.info(f"Successfully retrieved and using MedlinePlus info for: {lookup_message}")
                    
                    # Store the topic if it was extracted from provide_specific_info
                    if specific_info.get("extracted_topic") and conversation_context and 'user_facts' in conversation_context:
                        conversation_context['user_facts']['current_topic'] = specific_info["extracted_topic"]
                        logging.info(f"Updated current_topic from MedlinePlus: {specific_info['extracted_topic']}")
                    
                    # Add personalized warnings based on patient history if available
                    if patient_conditions or patient_medications or patient_allergies:
                        extracted_topic = specific_info.get("extracted_topic")
                        if extracted_topic:
                            relevant_history = await self._find_relevant_medical_history(
                                topic=extracted_topic,
                                conditions=patient_conditions,
                                medications=patient_medications,
                                allergies=patient_allergies
                            )
                            
                            if relevant_history:
                                relevant_info = "⚠️ Note: "
                                if len(relevant_history) == 1:
                                    relevant_info += f"You have a history of {relevant_history[0]}, which may affect management of {extracted_topic}."
                                else:
                                    conditions_list = ", ".join(relevant_history[:-1]) + " and " + relevant_history[-1]
                                    relevant_info += f"You have a history of {conditions_list}, which may affect management of {extracted_topic}."
                                
                                # Insert at the beginning of the messages
                                specific_info["messages"].insert(0, relevant_info)
                    
                    return specific_info
                else:
                    logging.info(f"No specific MedlinePlus info found for: {lookup_message}")
            except Exception as e:
                logging.error(f"Error retrieving MedlinePlus info: {str(e)}")
                # Continue to fallback if MedlinePlus retrieval fails
                
            # Fallback to symptom analyzer for general symptom queries
            try:
                symptoms = message
                severity = "MEDIUM"  # Default severity
                analysis = None  # Initialize analysis variable
                
                # Check for emergency keywords
                emergency_keywords = [
                    "chest pain", "can't breathe", "difficulty breathing", "stroke", 
                    "heart attack", "severe bleeding", "unconscious", "passed out"
                ]
                if any(keyword in message.lower() for keyword in emergency_keywords):
                    severity = "EMERGENCY"
                
                # For non-emergency cases, get a more detailed assessment from symptom analyzer
                else:
                    # Use the symptom analyzer if available
                    if hasattr(self, 'symptom_analyzer'):
                        # Check for red flags first
                        red_flag_result, red_flags = await self.symptom_analyzer.red_flag_checker(message)
                        if red_flag_result:
                            severity = "EMERGENCY"
                        else:
                            analysis = await self.symptom_analyzer.symptom_analyzer(message, patient_data)
                            if analysis:
                                symptom_severity = analysis.get('severity', 'MODERATE').upper()
                                # Map to our severity levels
                                if symptom_severity in ['SEVERE', 'CRITICAL']:
                                    severity = "HIGH"
                                elif symptom_severity in ['MODERATE']:
                                    severity = "MEDIUM"
                                elif symptom_severity in ['MILD']:
                                    severity = "LOW"
                
                # Use our new structured symptom response formatter
                recommendations = [
                    "Rest and monitor your symptoms",
                    "Stay hydrated with plenty of fluids",
                    "Consider over-the-counter medications for symptom relief"
                ]
                
                when_to_seek_help = [
                    "Symptoms worsen or don't improve within a few days",
                    "You develop a high fever (over 102°F/39°C)",
                    "You experience severe pain or discomfort",
                    "You have difficulty breathing, chest pain, or severe headache",
                    "You feel dizzy, confused, or disoriented"
                ]
                
                # Add specific recommendations based on keywords in the query
                if "headache" in message.lower():
                    recommendations.append("Rest in a quiet, darkened room")
                    recommendations.append("Apply a cold or warm compress to your head")
                    
                if "sore throat" in message.lower():
                    recommendations.append("Gargle with warm salt water (1/4 tsp salt in 8 oz water)")
                    recommendations.append("Use throat lozenges or throat sprays for temporary relief")
                
                # Add personalized warnings based on patient history if available
                personalized_note = None
                if patient_conditions or patient_medications or patient_allergies:
                    # Extract symptom keyphrase for relevance check
                    keyphrase = await self._extract_symptom_keyphrase(message)
                    if keyphrase:
                        relevant_history = await self._find_relevant_medical_history(
                            topic=keyphrase,
                            conditions=patient_conditions,
                            medications=patient_medications,
                            allergies=patient_allergies
                        )
                        
                        if relevant_history:
                            if len(relevant_history) == 1:
                                personalized_note = f"⚠️ Note: You have a history of {relevant_history[0]}, which may affect management of your symptoms."
                            else:
                                conditions_list = ", ".join(relevant_history[:-1]) + " and " + relevant_history[-1]
                                personalized_note = f"⚠️ Note: You have a history of {conditions_list}, which may affect management of your symptoms."
                
                from chatbot.views.utils.response_formatter import format_symptom_response
                messages = format_symptom_response(
                    symptoms=symptoms,
                    severity=severity,
                    recommendations=recommendations,
                    when_to_seek_help=when_to_seek_help,
                    personalized_note=personalized_note  # Add the personalized note if available
                )
                
                return {"messages": messages}
                
            except Exception as symptom_error:
                logging.error(f"Error in symptom analysis: {str(symptom_error)}")
                
                # Fall back to GPT for personalization if symptom analysis fails
                # Format patient information string for prompt
                patient_info = []
                if name != "there":
                    patient_info.append(f"Name: {name}")
                if age:
                    patient_info.append(f"Age: {age}")
                if gender:
                    patient_info.append(f"Gender: {gender}")
                
                # Add conditions, medications, and allergies to patient info
                if patient_conditions:
                    patient_info.append(f"Conditions: {', '.join(patient_conditions)}")
                if patient_medications:
                    patient_info.append(f"Medications: {', '.join(patient_medications)}")
                if patient_allergies:
                    patient_info.append(f"Allergies: {', '.join(patient_allergies)}")
                
                # Format patient info string or use generic greeting if no data available
                patient_line = f"Patient: {', '.join(patient_info)}" if patient_info else "Patient"
                    
                # Build a prompt for personalized medical advice
                prompt = f"""As a helpful medical advisor, provide personalized advice for this person:

{patient_line}
Symptom query: "{message}"
"""
                # Add conversation context if provided
                if conversation_context:
                    if conversation_context.get('summary'):
                        prompt += f"\nConversation context: {conversation_context['summary']}\n"
                    
                    if conversation_context.get('user_facts') and len(conversation_context['user_facts']) > 0:
                        prompt += f"\nRelevant user facts: {json.dumps(conversation_context['user_facts'])}\n"
                    
                    # Include a few recent messages for context if available
                    recent_messages = conversation_context.get('recent_messages', [])
                    if recent_messages and len(recent_messages) > 0:
                        prompt += "\nRecent conversation:\n"
                        # Get up to 3 most recent messages
                        for msg in recent_messages[-3:]:
                            speaker = "User" if msg.get('is_user', True) else "Assistant"
                            content = msg.get('message', '').strip()
                            if content:
                                prompt += f"{speaker}: {content}\n"
                
                # Add topic information if provided
                if topic:
                    prompt += f"\nSpecific topic focus: {topic}\n"
                elif is_follow_up and current_topic:
                    prompt += f"\nThis is a follow-up question about: {current_topic}\n"
                
                # Add additional data if provided
                if additional_data:
                    prompt += f"\nAdditional patient data: {additional_data}\n"
                
                prompt += """
Please provide:
1. A brief, factual explanation of what might be happening
2. 3-5 practical steps they can take right now to address their symptoms
3. When they should see a doctor

Keep your advice concise and direct, focusing on clear guidance.
IMPORTANT: End with a disclaimer about this being educational not professional medical advice.
"""

                # Get personalized advice from GPT
                from openai import AsyncOpenAI
                from django.conf import settings
                
                # Use symptom_analyzer's client if available, or create a new one
                if hasattr(self, 'symptom_analyzer') and hasattr(self.symptom_analyzer, 'openai_client'):
                    client = self.symptom_analyzer.openai_client
                elif hasattr(self, 'gpt_client'):
                    client = self.gpt_client
                elif hasattr(self, 'openai_client'):
                    client = self.openai_client
                else:
                    # Create a new client as fallback
                    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful medical advisor providing accurate, concise advice."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3  # Lower temperature for more factual responses
                )
                
                advice = response.choices[0].message.content.strip()
                
                # Split into paragraphs for better message formatting
                advice_paragraphs = [p.strip() for p in advice.split('\n') if p.strip()]
                
                # Add disclaimer if not already present
                from chatbot.views.utils.response_formatter import STANDARD_DISCLAIMER
                if not any(STANDARD_DISCLAIMER.lower() in p.lower() for p in advice_paragraphs):
                    advice_paragraphs.append(STANDARD_DISCLAIMER)
                
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
    
    async def _find_relevant_medical_history(self, topic, conditions=None, medications=None, allergies=None):
        """
        Find relevant medical history (conditions, medications, allergies) related to the given topic.
        
        Args:
            topic: The health issue/symptom topic
            conditions: List of patient conditions
            medications: List of patient medications
            allergies: List of patient allergies
            
        Returns:
            List of relevant medical history items
        """
        if not conditions and not medications and not allergies:
            return []
        
        try:
            # Build lists for the API call
            conditions_list = conditions or []
            medications_list = medications or []
            allergies_list = allergies or []
            
            # Use GPT to identify relevant medical history
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You are a medical expert that identifies relevant medical history.
                    A person is asking about a health issue, and you need to determine which aspects of their medical history
                    are relevant to this issue. Return a JSON object with relevant items:
                    {
                        "relevant_history": ["item1", "item2", ...]
                    }
                    """},
                    {"role": "user", "content": f"""Health issue/symptom: {topic}
                    
                    Patient medical history:
                    Conditions: {", ".join(conditions_list) if conditions_list else "None"}
                    Medications: {", ".join(medications_list) if medications_list else "None"}
                    Allergies: {", ".join(allergies_list) if allergies_list else "None"}
                    
                    Return only the JSON with relevant history items that could impact management of this health issue."""}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            relevant_items = result.get("relevant_history", [])
            
            return relevant_items
            
        except Exception as e:
            logging.error(f"Error finding relevant medical history: {str(e)}")
            return []
    
    async def _get_direct_medlineplus_info(self, keyphrase, condition_code):
        """
        Directly query MedlinePlus Connect with a keyphrase and SNOMED code.
        
        Args:
            keyphrase: The health issue/symptom keyphrase
            condition_code: The SNOMED CT code
            
        Returns:
            Dict with formatted messages or None if no info found
        """
        try:
            # Construct the MedlinePlus Connect API URL and parameters
            base_url = "https://connect.medlineplus.gov/service"
            params = {
                "mainSearchCriteria.v.c": condition_code,
                "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.96",  # SNOMED CT
                "mainSearchCriteria.v.dn": keyphrase.replace('_', ' '),
                "informationRecipient.language": "en",
                "knowledgeResponseType": "application/json"
            }
            
            # Make the API request
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(base_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    response_data = json.loads(response.text)
                    guideline_text = None
                    
                    # Extract information from the JSON structure
                    if 'feed' in response_data and 'entry' in response_data['feed']:
                        entries = response_data['feed']['entry']
                        if entries and len(entries) > 0:
                            # Try to get the summary content first
                            if 'summary' in entries[0] and '_value' in entries[0]['summary']:
                                guideline_text = entries[0]['summary']['_value'].strip()
                            
                            # If no summary, look for content or title
                            elif 'content' in entries[0] and '_value' in entries[0]['content']:
                                guideline_text = entries[0]['content']['_value'].strip()
                            
                            # Try title as last resort
                            elif 'title' in entries[0] and '_value' in entries[0]['title']:
                                guideline_text = entries[0]['title']['_value'].strip()
                
                    if guideline_text:
                        # We got guidelines, format the response
                        from chatbot.views.utils.response_formatter import format_medical_info_response
                        
                        formatted_messages = format_medical_info_response(
                            topic=keyphrase.replace('_', ' '),
                            summary=f"Here's information about {keyphrase.replace('_', ' ')} from MedlinePlus, a trusted medical resource:",
                            details={
                                "MEDICAL INFORMATION": guideline_text,
                                "RECOMMENDATIONS": [
                                    "Consult with a healthcare provider for a proper diagnosis",
                                    "Follow treatment plans as prescribed by your healthcare provider",
                                    "Keep track of your symptoms and what makes them better or worse"
                                ]
                            }
                        )
                        
                        # Make sure formatted_messages is a list of strings
                        if not all(isinstance(msg, str) for msg in formatted_messages):
                            formatted_messages = [str(msg) if not isinstance(msg, str) else msg for msg in formatted_messages]
                        
                        return {"messages": formatted_messages, "extracted_topic": keyphrase}
        
        except Exception as e:
            logging.error(f"Error in _get_direct_medlineplus_info: {str(e)}")
        
        return None

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
        
    async def resolve_condition_code(self, keyphrase: str) -> str:
        """
        Dynamically resolves a symptom/condition keyphrase to a SNOMED CT code for MedlinePlus queries.
        
        Args:
            keyphrase: The noun or phrase representing the health issue
            
        Returns:
            The SNOMED code if found, or None if not resolvable
        """
        logger.info(f"Attempting to resolve condition code for: {keyphrase}")
        
        # 1. First check our existing mapping
        if keyphrase.lower() in CONDITION_CODE_MAPPING:
            code = CONDITION_CODE_MAPPING[keyphrase.lower()]
            logger.info(f"Found existing code mapping for {keyphrase}: {code}")
            return code
            
        # 2. For compound phrases, try some normalization
        normalized_keyphrase = keyphrase.lower().replace(' ', '_')
        if normalized_keyphrase in CONDITION_CODE_MAPPING:
            code = CONDITION_CODE_MAPPING[normalized_keyphrase]
            logger.info(f"Found normalized code mapping for {keyphrase} -> {normalized_keyphrase}: {code}")
            return code
            
        # 3. Try checking for partial matches (e.g. if "knee pain" is in mapping but keyphrase is "severe knee pain")
        for existing_condition in CONDITION_CODE_MAPPING:
            if existing_condition in keyphrase.lower() or keyphrase.lower() in existing_condition:
                code = CONDITION_CODE_MAPPING[existing_condition]
                logger.info(f"Found partial match mapping for {keyphrase} -> {existing_condition}: {code}")
                return code
                
        # 4. If not found, use GPT to suggest a SNOMED code
        try:
            logger.info(f"No direct mapping found for {keyphrase}, querying GPT for SNOMED code")
            
            # Use OpenAI to map to a standard condition code
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You are a medical coding expert that maps symptoms to SNOMED CT codes.
                    Return a JSON object with the following structure:
                    {
                        "snomed_code": "string", 
                        "condition_name": "string",
                        "confidence": float,
                        "explanation": "string"
                    }
                    If unable to map with confidence, set snomed_code to null."""},
                    {"role": "user", "content": f"""Map this health issue description to a SNOMED CT code: "{keyphrase}"
                    
                    Some examples of known mappings:
                    - "back pain" -> "161891005"
                    - "headache" -> "25064002"
                    - "high blood pressure" -> "38341003"
                    - "diabetes" -> "44054006"
                    
                    Please return only the JSON object with the mapping."""}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Parse the response
            mapping_result = json.loads(response.choices[0].message.content)
            
            # Check if we got a valid code with good confidence
            if (mapping_result.get("snomed_code") and 
                mapping_result.get("confidence", 0) > 0.7 and
                mapping_result.get("condition_name")):
                
                code = mapping_result["snomed_code"]
                condition_name = mapping_result["condition_name"].lower().replace(' ', '_')
                
                # Add to our local mapping for future use
                CONDITION_CODE_MAPPING[condition_name] = code
                logger.info(f"Added new mapping from GPT: {condition_name} -> {code}")
                
                return code
            else:
                logger.info(f"GPT could not map with confidence: {mapping_result}")
                return None
                
        except Exception as e:
            logger.error(f"Error querying GPT for SNOMED code: {str(e)}")
            return None

    async def provide_specific_info(self, symptom_description):
        """
        Provide specific information for the symptom using MedlinePlus guidelines
        when available, and fallback to predefined guidance when not.
        """
        # Extract keyphrase from symptom description
        keyphrase = await self._extract_symptom_keyphrase(symptom_description)
        
        if not keyphrase:
            # If we couldn't extract a keyphrase, try the older location-based approach
            return await self._legacy_provide_specific_info(symptom_description)
            
        logger.info(f"Extracted keyphrase: {keyphrase} from symptom: {symptom_description}")
        
        # Try to resolve the SNOMED code for the keyphrase
        condition_code = await self.resolve_condition_code(keyphrase)
        
        if condition_code:
            # We have a code, try to get MedlinePlus info
            try:
                # Use a direct call to get_medlineplus_guidelines with the keyphrase and code
                # This is more flexible than the previous approach that required entries in CONDITION_CODE_MAPPING
                base_url = "https://connect.medlineplus.gov/service"
                params = {
                    "mainSearchCriteria.v.c": condition_code,
                    "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.96",  # SNOMED CT
                    "mainSearchCriteria.v.dn": keyphrase.replace('_', ' '),
                    "informationRecipient.language": "en",
                    "knowledgeResponseType": "application/json"
                }
                
                # Make the API request
                import httpx
                async with httpx.AsyncClient() as client:
                    # Make the API request with proper error handling
                    response = await client.get(base_url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        try:
                            # Parse the JSON response
                            response_data = json.loads(response.text)
                            guideline_text = None
                            
                            # Extract information from the JSON structure
                            # MedlinePlus Connect uses an Atom feed structure
                            if 'feed' in response_data and 'entry' in response_data['feed']:
                                entries = response_data['feed']['entry']
                                if entries and len(entries) > 0:
                                    # Try to get the summary content first
                                    if 'summary' in entries[0] and '_value' in entries[0]['summary']:
                                        guideline_text = entries[0]['summary']['_value'].strip()
                                    
                                    # If no summary, look for content or title
                                    elif 'content' in entries[0] and '_value' in entries[0]['content']:
                                        guideline_text = entries[0]['content']['_value'].strip()
                                    
                                    # Try title as last resort
                                    elif 'title' in entries[0] and '_value' in entries[0]['title']:
                                        guideline_text = entries[0]['title']['_value'].strip()
                        
                            if guideline_text:
                                # We got guidelines, format the response
                                from chatbot.views.utils.response_formatter import format_medical_info_response
                                
                                formatted_messages = format_medical_info_response(
                                    topic=keyphrase.replace('_', ' '),
                                    summary=f"Here's information about {keyphrase.replace('_', ' ')} from MedlinePlus, a trusted medical resource:",
                                    details={
                                        "MEDICAL INFORMATION": guideline_text,
                                        "RECOMMENDATIONS": [
                                            "Consult with a healthcare provider for a proper diagnosis",
                                            "Follow treatment plans as prescribed by your healthcare provider",
                                            "Keep track of your symptoms and what makes them better or worse"
                                        ]
                                    }
                                )
                                
                                # Make sure formatted_messages is a list of strings
                                if not all(isinstance(msg, str) for msg in formatted_messages):
                                    formatted_messages = [str(msg) if not isinstance(msg, str) else msg for msg in formatted_messages]
                                
                                return {"messages": formatted_messages, "extracted_topic": keyphrase}
                            
                        except json.JSONDecodeError as json_error:
                            logger.error(f"JSON parsing error for MedlinePlus response: {json_error}")
                    
            except Exception as e:
                logger.error(f"Error getting MedlinePlus info for {keyphrase}: {str(e)}")
        
        # Generate a generic fallback response if we couldn't get MedlinePlus info
        messages = [
            f"For {keyphrase.replace('_', ' ')}:",
            "- Rest and avoid exacerbating activities",
            "- Apply ice or heat as appropriate",
            "- Consider over-the-counter analgesics",
            "- Consult your healthcare provider if symptoms persist beyond 3 days"
        ]
        
        return {"messages": messages, "extracted_topic": keyphrase}
    
    async def _extract_symptom_keyphrase(self, symptom_description):
        """
        Extract the key noun phrase representing the health issue from the user's description.
        Uses GPT for high-quality entity extraction.
        """
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You are a medical NLP expert that extracts key medical terms.
                    Extract the main health issue/symptom from the user's message as a simple noun phrase.
                    Return a JSON object with the following structure:
                    {
                        "keyphrase": "string", 
                        "normalized_term": "string"
                    }
                    For example, if user says "I've been having trouble sleeping for weeks",
                    you would return {"keyphrase": "trouble sleeping", "normalized_term": "insomnia"}"""},
                    {"role": "user", "content": f"""Extract the main health issue from this text: "{symptom_description}"
                    
                    Return only the JSON object with the keyphrase and normalized term."""}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Return normalized term if available, otherwise the keyphrase
            keyphrase = result.get("normalized_term") or result.get("keyphrase")
            
            if keyphrase:
                return keyphrase.lower().strip()
            return None
            
        except Exception as e:
            logger.error(f"Error extracting keyphrase from symptom description: {str(e)}")
            return None
    
    # Keep the legacy method for backward compatibility and as a fallback
    async def _legacy_provide_specific_info(self, symptom_description):
        """
        Legacy implementation of provide_specific_info using location-based approach.
        """
        # Extract location and type of pain
        location = None
        pain_words = ['ache', 'pain', 'hurt', 'sore', 'discomfort']
        
        # Simple location extraction
        body_parts = ['head', 'back', 'chest', 'stomach', 'leg', 'arm', 'foot', 'hand', 'knee', 'ankle']
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
            'hand': 'hand_pain',
            'ankle': 'ankle_pain'
        }
        
        # Try to get MedlinePlus information if available
        medline_info = None
        condition_name = None
        
        if location in condition_mapping:
            # Add to CONDITION_CODE_MAPPING if not already there
            condition_name = condition_mapping[location]
            if condition_name in CONDITION_CODE_MAPPING:
                try:
                    medline_info = await get_medlineplus_guidelines(condition_name)
                    logging.info(f"Retrieved MedlinePlus info for {condition_name}: {medline_info}")
                except Exception as e:
                    logging.error(f"Error getting MedlinePlus info for {condition_name}: {str(e)}")
        
        # If we got MedlinePlus info, use it with better formatting
        if medline_info and medline_info.strip():
            logging.info(f"Found MedlinePlus info for {location} pain")
            
            # Import the response formatter for consistent formatting
            from chatbot.views.utils.response_formatter import format_medical_info_response
            
            # Format the response with proper structure
            formatted_messages = format_medical_info_response(
                topic=f"{location} pain",
                summary=f"Here's information about {location} pain from MedlinePlus, a trusted medical resource:",
                details={
                    "MEDICAL INFORMATION": medline_info,
                    "RECOMMENDATIONS": [
                        "Consult with a healthcare provider for a proper diagnosis",
                        "Follow treatment plans as prescribed by your healthcare provider",
                        "Keep track of your symptoms and what makes them better or worse"
                    ]
                }
            )
            
            # Make sure formatted_messages is a list of strings
            if not all(isinstance(msg, str) for msg in formatted_messages):
                # Convert any non-string elements to strings
                formatted_messages = [str(msg) if not isinstance(msg, str) else msg for msg in formatted_messages]
            
            return {"messages": formatted_messages, "extracted_topic": condition_name}
        
        # If no MedlinePlus info, use the more general AI-driven symptom analysis
        # by falling through to the general handler
        
        # Try to trigger a more personalized AI-based analysis instead
        try:
            analysis_response = await self.handle_symptom_query(
                f"{location} pain {symptom_description}", 
                None,  # No patient data needed for general response
                topic=condition_name  # Pass the identified condition as the topic
            )
            
            if analysis_response and "messages" in analysis_response and analysis_response["messages"]:
                # If we got a good AI-generated response, use it
                analysis_response["extracted_topic"] = condition_name
                return analysis_response
        except Exception as ai_error:
            logging.error(f"Error getting AI-based analysis: {str(ai_error)}")
        
        # As a last resort, fall back to predefined guidance
        messages = []
        
        if location == 'back':
            messages = [
                "For back pain:",
                "- Apply ice for the first 48-72 hours, then heat",
                "- Gentle stretching may help, but avoid strenuous activity",
                "- Over-the-counter pain relievers like ibuprofen may help reduce inflammation"
            ]
            condition_name = "back_pain"
        elif location == 'head':
            messages = [
                "For headaches:",
                "- Rest in a quiet, dark room",
                "- Stay hydrated",
                "- Try a cold compress on your forehead",
                "- Track your headaches to identify patterns and triggers"
            ]
            condition_name = "headache"
        elif location == 'leg':
            messages = [
                "For leg pain:",
                "- Rest and elevate the leg when possible",
                "- Apply ice to reduce swelling",
                "- Gentle stretching may help with muscle discomfort",
                "- Avoid prolonged standing if it worsens the pain"
            ]
            condition_name = "leg_pain"
        else:
            messages = [
                f"For {location} pain:",
                "- Rest the affected area when possible",
                "- Apply ice to reduce swelling and inflammation",
                "- Over-the-counter pain relievers may help with discomfort",
                "- Consult your healthcare provider if pain persists or worsens"
            ]
            condition_name = f"{location}_pain"
            
        return {"messages": messages, "extracted_topic": condition_name}

    async def handle_issue_report(self, issue_data: Dict[str, Any], openai_client: AsyncGPT4Client) -> Dict[str, Any]:
        """Handle issue report and generate appropriate response."""
        try:
            # Extract condition and symptoms
            condition = issue_data.get('condition', '').lower()
            symptoms = issue_data.get('symptoms', [])
            
            # Get evidence-based guidelines
            guidelines = get_evidence_based_guidelines([condition])
            
            # Generate personalized advice
            advice = await self.get_personalized_advice(condition, symptoms, guidelines, openai_client)
            
            # Create history note with proper format
            history_note = {
                'type': 'issue_report',
                'condition': condition,
                'condition_code': CONDITION_CODE_MAPPING.get(condition, ''),
                'confidence_level': 'high',
                'symptoms': symptoms,
                'advice': advice
            }
            
            return {
                'status': 'success',
                'advice': advice,
                'history_note': history_note
            }
            
        except Exception as e:
            logger.error(f"Error handling issue report: {str(e)}")
            return {
                'status': 'error',
                'message': 'Failed to process issue report'
            }

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
logger.debug("Personalized medical advice service initialization complete")