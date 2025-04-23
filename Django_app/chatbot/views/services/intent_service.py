from collections.abc import Coroutine
import logging
import json
import re
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional

from openai import AsyncOpenAI
from django.conf import settings
from asgiref.sync import sync_to_async

# FHIR and Language Imports
from fhirclient.client import FHIRClient
from chatbot.views.config import config  # Assuming this contains FHIR server settings
from chatbot.views.services.language_service import LanguageService

# Load your OpenAI model name from a constants file or environment
from ..utils.constants import OPENAI_MODEL

logger = logging.getLogger('chatbot')
logger.debug("Intent service module loaded")
# Global fallback cache for GPT fallback responses (to reduce redundant API calls)
FALLBACK_CACHE = {}

# ============================================
#   FHIR Client Initialization (async)
# ============================================
#figure out if any of this shit is necessary and wht it is exactly
def get_async_fhir_client():
    """
    Asynchronously get a configured FHIR client instance.
    Ensures that FHIR server methods are available as async functions.
    """
    settings_dict = {
        'app_id': 'anna_chatbot',
        'api_base': settings.FHIR_SERVER_URL
    }
    try:
        fhir_client = FHIRClient(settings=settings_dict)
        # Convert blocking methods to async versions
        fhir_client.server.request_json = sync_to_async(fhir_client.server.request_json, thread_sensitive=False)
        fhir_client.server.update = sync_to_async(fhir_client.server.update, thread_sensitive=False)
        fhir_client.server.create = sync_to_async(fhir_client.server.create, thread_sensitive=False)
        fhir_client.server.delete = sync_to_async(fhir_client.server.delete, thread_sensitive=False)
        fhir_client.server.perform_request = sync_to_async(fhir_client.server.perform_request, thread_sensitive=False)
        logger.info("Asynchronous FHIR client initialized successfully")
        return fhir_client
    except Exception as e:
        logger.error(f"Failed to initialize asynchronous FHIR client: {e}")
        raise

# ============================================
#   OpenAI Client Initialization
# ============================================

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
language_service = LanguageService()

# ============================================
#   Intent Enumeration and Data Class
# ============================================

class Intent(Enum):
    SET_APPOINTMENT = 'set_appointment'
    SHOW_APPOINTMENTS = 'show_appointments'
    MEDICAL_RECORD_QUERY = 'medical_record_query'
    MEDICAL_INFO_QUERY = 'medical_info_query'
    SYMPTOM_REPORT = 'symptom_report'
    LAB_RESULTS_QUERY = 'lab_results_query'
    LAB_RESULTS = 'lab_results'
    CAPABILITIES = 'capabilities'
    EXPLANATION_QUERY = 'explanation_query'
    EMAIL_VERIFICATION = 'email_verification'
    RESET_CONTEXT = 'reset_context'
    DELETE_CONTEXT = 'delete_context'
    GREETING = 'greeting'
    CONDITION_QUERY = 'condition_query'
    MENTAL_HEALTH_QUERY = 'mental_health_query'
    SCREENING = 'screening'
    ISSUE_REPORT = 'issue_report'  # New intent for any user-reported health issue
    UNKNOWN = 'unknown'

@dataclass
class IntentData:
    """
    A structured container for intent detection results.
    """
    intent: Intent
    confidence: float
    entities: Dict[str, str]
    original_text: str = None
    context_type: str = None

# ============================================
#   Pre-compiled Regex Patterns
# ============================================

# --- Appointment Patterns ---
APPOINTMENT_KEYWORDS = (
    r"(?:book|schedule|make|arrange|reserve|organize|plan|fix|request|create|initiate|set(?:\s*up)?|secure|hold|slot|enroll|register|put\s+down)"
)
APPOINTMENT_PATTERNS_RAW = [
    fr"{APPOINTMENT_KEYWORDS}\s+(?:an|a)?\s+(?:appointment|visit|check[-\s]*up)",
    fr"(?:i|we|would like to|i'd like to|i need to|i want to)\s+{APPOINTMENT_KEYWORDS}\s+(?:an|a)?\s+(?:appointment|visit|check[-\s]*up)",
    fr"need\s+to\s+{APPOINTMENT_KEYWORDS}\s+(?:an|a)?\s+(?:appointment|visit|check[-\s]*up)",
    fr"want\s+to\s+{APPOINTMENT_KEYWORDS}\s+(?:an|a)?\s+(?:appointment|visit|check[-\s]*up)"
]
COMPILED_APPOINTMENT_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in APPOINTMENT_PATTERNS_RAW]

APPOINTMENT_VIEW_PATTERNS_RAW = [
    r'(?:show|view|see|check|list|get|display|pull\s+up|fetch|retrieve)\s+(?:my|all|any|upcoming)?\s+appointments?',
    r'what\s+(?:appointments?|bookings?)\s+do\s+i\s+have(?:\s+scheduled)?',
    r'(?:my|all|upcoming|scheduled)\s+appointments?'
]
COMPILED_APPOINTMENT_VIEW_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in APPOINTMENT_VIEW_PATTERNS_RAW]

# --- Symptom Patterns ---
SYMPTOM_PATTERNS_RAW = {
    'pain': [r'hurts?', r'aching?', r'pain(?:ful)?', r'sore', r'tender', r'burning',
             r'sharp\s+pain', r'dull\s+pain', r'throbbing', r'joint', r'joints',
             r'ankle', r'elbow', r'knee', r'leg\s+pain', r'foot\s+pain', r'back\s+ache'],
    'respiratory': [r'cough(?:ing)?', r'breathing', r'short\s+of\s+breath', r'wheez(?:e|ing)',
                    r'chest\s+tight(?:ness)?', r"can't\s+breathe", r'difficulty\s+breathing',
                    r'asthma', r'lung\s+pain'],
    'gastrointestinal': [r'stomach', r'nausea(?:ted)?', r'vomiting', r'diarrhea', r'constipation',
                         r'abdominal\s+pain', r'indigestion', r'cramps?', r'gastro'],
    'neurological': [r'headache', r'dizzy', r'migraine', r'faint(?:ing)?', r'numbness',
                     r'tingling', r'balance', r'vision', r'hearing', r'seizure', r'epilepsy'],
    'general': [r'fever(?:ish)?', r'tired(?:ness)?', r'fatigue', r'weak(?:ness)?', r'exhausted',
                r'not\s+feeling\s+well', r'unwell', r'sick', r'ill'],
    'musculoskeletal': [r'joint\s+pain', r'muscle\s+pain', r'stiffness', r'swelling',
                        r'limited\s+movement', r'difficulty\s+moving', r'arthritis',
                        r'sprain', r'strain', r'inflammation']
}
COMPILED_SYMPTOM_PATTERNS = {}
for category, patterns in SYMPTOM_PATTERNS_RAW.items():
    COMPILED_SYMPTOM_PATTERNS[category] = [re.compile(p, flags=re.IGNORECASE) for p in patterns]

# --- Medical Record Patterns ---
MEDICAL_RECORD_PATTERNS_RAW = [
    r'(?:show|view|see|access|get|pull\s+up|retrieve)\s+(?:my|all)?\s+(?:medical|health)?\s+records?',
    r'(?:my|full|complete)\s+(?:medical|health)?\s+records?',
    r'history',
    r'(?:my|the)\s+(?:chart|ehr|patient\s*portal|medical\s*file)'
]
COMPILED_MEDICAL_RECORD_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in MEDICAL_RECORD_PATTERNS_RAW]

# --- Medical Info Patterns ---
MEDICAL_INFO_PATTERNS_RAW = [
    r'what\s+is', r'tell\s+me\s+about', r'explain', r'information\s+about',
    r'learn\s+about', r'understand', r'how\s+do\s+i\s+know\s+if', r'how\s+can\s+i\s+tell\s+if',
    r'what\s+are\s+the\s+signs\s+of', r'how\s+do\s+you\s+know\s+if', r'how\s+to\s+tell\s+if',
    r'can\s+you\s+provide\s+info', r'give\s+me\s+information', r'differences?\s+between'
]
COMPILED_MEDICAL_INFO_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in MEDICAL_INFO_PATTERNS_RAW]

# --- Mental Health Patterns ---
MENTAL_HEALTH_PATTERNS_RAW = [
    r'depression', r'anxiety', r'(?:mental|emotional)\s+health', r'sad(?:ness)?',
    r'unhappy', r'stress(?:ed)?', r'mood', r'therap(?:y|ist)', r'psychological',
    r'crying', r'hopeless(?:ness)?', r'worthless(?:ness)?', r'panic', r'insomnia',
    r'burnout', r'trauma', r'ptsd', r'bipolar', r'schizophrenia', r'suicid(?:e|al)',
    r'self[-\s]*harm', r'counseling'
]
COMPILED_MENTAL_HEALTH_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in MENTAL_HEALTH_PATTERNS_RAW]

# --- Condition Patterns ---
CONDITION_PATTERNS_RAW = [
    r'(?:my|current|existing)\s+conditions?', r'medical\s+conditions?',
    r'what\s+(?:conditions?|illnesses?)\s+do\s+i\s+have', r'what\s+am\s+i\s+diagnosed\s+with',
    r'health\s+conditions?', r'ongoing\s+diagnoses?', r'active\s+conditions?'
]
COMPILED_CONDITION_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in CONDITION_PATTERNS_RAW]

# --- Screening Patterns ---
# Only match screening intent in the context of a response to a screening reminder
# Rather than detecting general questions about screenings/health checks
SCREENING_PATTERNS_RAW = [
    r'screening\s+reminder', r'responding\s+to\s+screening',
    r'about\s+(?:the|my|your)\s+screening\s+(?:reminder|notification|message)',
    r'received\s+(?:a|the)\s+screening'
]
COMPILED_SCREENING_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in SCREENING_PATTERNS_RAW]

# --- Lab Result Patterns ---
LAB_RESULT_PATTERNS_RAW = [
    r".*\b(?:cholesterol|glucose|hdl|ldl|triglycerides|potassium|sodium|chloride|bicarbonate|bun|creatinine|calcium|protein|albumin|bilirubin|ast|alt|alkaline\s+phosphatase|ggt|tsh|t4|t3|cortisol|testosterone|estradiol|progesterone|psa|uric\s+acid|crp|esr|inr|pt|aptt|d-dimer|troponin|ck|ldh|amylase|lipase|magnesium|phosphorus|iron|ferritin|transferrin|vitamin\s?b12|folate|vitamin\s?d|platelets|hemoglobin|leukocytes).*(?:high|low|normal|level|range|result|test|value|number).*",
    r".*\bwhat.*\b(?:do|does|about|concerning).*\b(?:my|these|those)?.*\b(?:test|result|level|value|number).*",
    r".*\b(?:my|the|latest|recent|previous|past).*\b(?:test|result|level|value|number).*\b(?:high|low|normal|range).*",
    r".*\b(?:test|result|level|value|number).*(?:okay|ok|good|bad|normal|abnormal|concerning|worrying).*",
    r"(?:what|how|why|when|where|which)\s+(?:is|are|do|does|can|could|should|would)?\s+.*?\s+(?:about|concerning|regarding|related\s+to|pertaining\s+to|mean|levels?|values?|numbers?|results?|tests?|readings?|measurements?)\b",
    r".*\b(?:lab|test|result|level|value|number)\b.*(?:from|on|in|at|for|during)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?|\s+in)?\s*(?:\d{4}|\d{2})?",
    r"\d{4}-\d{2}-\d{2}",
    r"\d{1,2}/\d{1,2}/\d{2,4}",
]
COMPILED_LAB_RESULT_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in LAB_RESULT_PATTERNS_RAW]

ADDITIONAL_LAB_PATTERNS_RAW = [
    r".*(?:lab|labs?|test|tests?)\s+results?.*",
    r".*(?:blood|urine)\s+test.*",
    r".*my\s+(?:recent|latest|last)\s+results.*",
    r".*results?\s+for.*",
    r".*my\s+levels.*"
]
COMPILED_ADDITIONAL_LAB_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in ADDITIONAL_LAB_PATTERNS_RAW]

# --- Capability Patterns ---
CAPABILITY_PATTERNS_RAW = [
    r"(?:what\s+can\s+you\s+do|what\s+are\s+your\s+capabilities|what\s+do\s+you\s+do|help|how\s+can\s+you\s+help\s+me|what\s+are\s+you\s+able\s+to\s+do|show\s+me\s+what\s+you\s+can\s+do|list\s+capabilities|list\s+functions|what\s+features\s+do\s+you\s+have)"
]
COMPILED_CAPABILITY_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in CAPABILITY_PATTERNS_RAW]

# --- Explanation Patterns ---
EXPLANATION_PATTERNS_RAW = [
    r"(?:how\s+do\s+you\s+explain|can\s+you\s+explain|what\s+does\s+.*?\s+mean|explain\s+.*?\s+to\s+me|help\s+me\s+understand|what\s+is\s+the\s+meaning\s+of|could\s+you\s+clarify|what\s+are|how\s+do\s+.*?\s+work|explain\s+the\s+difference)"
]
COMPILED_EXPLANATION_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in EXPLANATION_PATTERNS_RAW]

# --- Greeting Patterns ---
GREETING_PATTERNS_RAW = [
    r'\b(?:hi|hello|hey|hii|heyy|yo|hiya|greetings?|wassup|what\'s\s*up|sup|good\s+(?:morning|afternoon|evening|day))\b'
]
COMPILED_GREETING_PATTERNS = [re.compile(p, flags=re.IGNORECASE) for p in GREETING_PATTERNS_RAW]

# ============================================
#   Helper Function to Extract Medical Topic
# ============================================
def extract_medical_topic(message: str) -> str:
    """
    Removes common prompt phrases so that the core topic is isolated.
    """
    patterns_to_remove = [
        'what is', 'tell me about', 'explain', 'information about',
        'learn about', 'understand', 'differences? between'
    ]
    cleaned_message = message
    for pattern in patterns_to_remove:
        cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE).strip()
    return cleaned_message

# ============================================
#   Main Intent Detection Function (Improved)
# ============================================
async def detect_intent(
    user_input: str,
    conversation_context: Optional[dict] = None,
    last_intent: Optional[str] = None
) -> Dict[str, any]:
    """
    Determines the user's intent using a layered approach:
      1. Special-case handling (digit input, email verification, context deletion/reset)
      2. Regex-based matching using precompiled patterns.
      3. Context-aware handling for short or anaphoric queries.
      4. A GPT fallback with few-shot examples and caching.
    """
    logger.info("=== STARTING INTENT DETECTION ===")
    logger.info(f"Input message: {user_input!r}")

    if not user_input or not isinstance(user_input, str):
        logger.error("Invalid user input: either None or not a string.")
        return {
            "intent": Intent.UNKNOWN.value,
            "confidence": 0.1,
            "entities": {},
            "original_text": str(user_input)
        }

    original_message = user_input.lower().strip()
    logger.debug(f"Processed message: {original_message!r}")

    # --- 1. Special Cases ---
    # 1a. Digit input during booking state
    if conversation_context and original_message.isdigit() and conversation_context.get('booking_state'):
        logger.info("Special case: Digit input during booking state detected.")
        return {
            "intent": Intent.SET_APPOINTMENT.value,
            "confidence": 1.0,
            "entities": {"selection": original_message, "original_text": user_input, "context": "booking_flow"}
        }

    # 1b. Email Verification
    try:
        email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', flags=re.IGNORECASE)
        if '@' in original_message:
            match_result = email_pattern.match(original_message)
            if match_result:
                matched_email = match_result.group(0)
                logger.info("Special case: Email verification match detected.")
                return {
                    "intent": Intent.EMAIL_VERIFICATION.value,
                    "confidence": 1.0,
                    "entities": {"email": matched_email, "original_text": user_input,
                                 "action": "verify", "context_type": "authentication"}
                }
    except Exception as e:
        logger.error(f"Error in email verification block: {e}")

    # 1c. Delete Context
    delete_commands = ["delete context", "clear context", "reset all", "delete contxt", "remove context", "erase context", "forget everything"]
    if any(cmd in original_message for cmd in delete_commands):
        logger.info("Special case: Delete context command recognized.")
        return {
            "intent": Intent.DELETE_CONTEXT.value,
            "confidence": 1.0,
            "entities": {"action": "delete", "topic": "system", "original_text": user_input}
        }

    # 1d. Reset Context
    reset_patterns = [re.compile(p, flags=re.IGNORECASE) for p in [
        r"(?:i\s+)?(?:am\s+)?not\s+talking\s+about",
        r"(?:i\s+)?don'?t\s+mean",
        r"different\s+(?:topic|subject)",
        r"something\s+else",
        r"forget\s+the\s+previous\s+topic"
    ]]
    if any(pattern.search(original_message) for pattern in reset_patterns):
        excluded_topic_match = re.search(r"(?:about|mean)\s+(\w+)", original_message)
        excluded_topic = excluded_topic_match.group(1) if excluded_topic_match else None
        logger.info("Special case: Reset context command recognized.")
        return {
            "intent": Intent.RESET_CONTEXT.value,
            "confidence": 1.0,
            "entities": {"original_text": user_input, "excluded_topic": excluded_topic}
        }

    # --- 2. Regex-Based Detection ---
    # 2.1 Greeting
    if any(pattern.search(original_message) for pattern in COMPILED_GREETING_PATTERNS):
        logger.info("Regex detection: Greeting pattern matched.")
        return {
            "intent": Intent.GREETING.value,
            "confidence": 1.0,
            "entities": {},
            "original_text": user_input
        }

    # 2.2 Appointment Booking
    if any(pattern.search(original_message) for pattern in COMPILED_APPOINTMENT_PATTERNS):
        logger.info("Regex detection: Appointment booking pattern matched.")
        return {
            "intent": Intent.SET_APPOINTMENT.value,
            "confidence": 0.95,
            "entities": {"topic": original_message, "original_text": user_input}
        }

    # 2.3 Appointment Viewing
    if any(pattern.search(original_message) for pattern in COMPILED_APPOINTMENT_VIEW_PATTERNS):
        logger.info("Regex detection: Appointment viewing pattern matched.")
        return {
            "intent": Intent.SHOW_APPOINTMENTS.value,
            "confidence": 0.95,
            "entities": {"action": "view", "original_text": user_input}
        }

    # 2.4 Health Issue Detection (combines the new issue_report intent with traditional symptom reporting)
    # Check for general health issue indicators first 
    health_terms = [
        r'\b(?:symptom|feeling|suffering|experiencing|having)\b',
        r'\b(?:pain|ache|sore|hurt|discomfort)\b',
        r'\b(?:sick|ill|unwell|not well)\b',
        r'(?:problem with|issue with|trouble with)',
        r'\b(?:diagnosed|condition)\b',
        r'(?:can\'t sleep|insomnia|tired|fatigue)',
        r'\b(?:cough|fever|rash|dizziness|swelling)\b'
    ]
    
    is_general_health_issue = False
    for pattern in health_terms:
        if re.search(pattern, original_message, re.IGNORECASE):
            is_general_health_issue = True
            logger.info(f"Detected general health issue pattern: {pattern}")
            break
    
    # If it's a general health issue but not matching specific symptom categories,
    # use the new issue_report intent
    if is_general_health_issue:
        # Extract a symptom keyphrase if possible (this will be None if no service exists yet)
        symptom_keyphrase = None
        # We can't directly call the medical_advice_service here since it's not available
        # The actual keyphrase extraction will happen in the handler
        
        logger.info(f"Regex detection: General health issue detected, using issue_report intent.")
        return {
            "intent": Intent.ISSUE_REPORT.value,
            "confidence": 0.95,
            "entities": {
                "symptom_description": original_message, 
                "original_text": user_input,
                "symptom_keyphrase": symptom_keyphrase  # Will be None here, extracted later in handler
            }
        }
    
    # Fall back to traditional symptom category detection for specific symptoms
    for category, patterns in COMPILED_SYMPTOM_PATTERNS.items():
        if any(pattern.search(original_message) for pattern in patterns):
            logger.info(f"Regex detection: Symptom report pattern matched for category {category}.")
            return {
                "intent": Intent.SYMPTOM_REPORT.value,
                "confidence": 0.95,
                "entities": {"symptom_category": category, "symptom_description": original_message, "original_text": user_input}
            }

    # 2.5 Anaphora / Short Query Handling
    anaphora_patterns = {
        'it': re.compile(r'\b(it|this|that|these|those)\b', flags=re.IGNORECASE),
        'levels': re.compile(r'\b(levels|values|numbers|results)\b', flags=re.IGNORECASE),
        'change': re.compile(r'\b(increase|decrease|improve|change|modify)\b', flags=re.IGNORECASE)
    }
    
    # Debug logging for follow-up detection
    logger.debug(f"Checking for anaphora in: {original_message}")
    if conversation_context:
        current_topic_info = conversation_context.get('current_topic', {})
        logger.debug(f"With context: {current_topic_info}")
        logger.debug(f"Context type: {type(current_topic_info)}")
        logger.debug(f"Full conversation context: {conversation_context}")
    else:
        logger.debug("No conversation context provided")
        
    # Track which pattern matched for better debugging
    matched_pattern = None
    for pattern_name, pattern in anaphora_patterns.items():
        if pattern.search(original_message):
            matched_pattern = pattern_name
            logger.debug(f"Matched anaphora pattern: {pattern_name}")
            break
    
    if any(pattern.search(original_message) for pattern in anaphora_patterns.values()) and conversation_context and conversation_context.get('current_topic'):
        current_topic = conversation_context['current_topic']
        logger.debug(f"Current topic: {current_topic}")
        logger.debug(f"Current topic type: {type(current_topic)}")
        if isinstance(current_topic, dict):
            logger.debug(f"Topic name: {current_topic.get('name')}")
            logger.debug(f"Topic type: {current_topic.get('type')}")
        
        # Map the current topic type to the appropriate intent
        topic_type = current_topic.get('type', '')
        logger.debug(f"Topic type: {topic_type}")
        
        # Handle different types of follow-up questions based on the current topic
        if topic_type == 'lab_result' or topic_type == 'lab_results' or topic_type == 'lab_results_query':
            logger.info("Anaphora resolution: Lab result context detected in conversation context.")
            logger.debug("Identified as lab result follow-up")
            return {
                "intent": Intent.LAB_RESULTS_QUERY.value,
                "confidence": 0.9,
                "entities": {"action": "followup", "topic": current_topic.get('name'),
                             "original_text": user_input, "reference_range": current_topic.get('reference_range'),
                             "last_value": current_topic.get('last_value'), "context_type": "anaphora_resolution"}
            }
        elif topic_type == 'symptom_report' or topic_type == 'symptoms':
            logger.info("Anaphora resolution: Symptom context detected in conversation context.")
            logger.debug("Identified as symptom follow-up")
            return {
                "intent": Intent.SYMPTOM_REPORT.value,
                "confidence": 0.9,
                "entities": {"action": "followup", "topic": current_topic.get('name'),
                             "original_text": user_input, "context_type": "anaphora_resolution"}
            }
        elif topic_type == 'medication' or topic_type == 'medications':
            logger.info("Anaphora resolution: Medication context detected in conversation context.")
            print("DEBUG-INTENT-FOLLOWUP-8: Identified as medication follow-up")
            return {
                "intent": Intent.MEDICAL_INFO_QUERY.value,
                "confidence": 0.9,
                "entities": {"action": "followup", "topic": current_topic.get('name'),
                             "original_text": user_input, "context_type": "anaphora_resolution"}
            }
        elif topic_type == 'appointment' or topic_type == 'scheduling':
            logger.info("Anaphora resolution: Appointment context detected in conversation context.")
            print("DEBUG-INTENT-FOLLOWUP-9: Identified as appointment follow-up")
            return {
                "intent": Intent.SHOW_APPOINTMENTS.value, 
                "confidence": 0.9,
                "entities": {"action": "followup", "topic": current_topic.get('name'),
                             "original_text": user_input, "context_type": "anaphora_resolution"}
            }
        else:
            # General follow-up for other topics
            logger.info(f"Anaphora resolution: General follow-up to topic {topic_type}")
            logger.debug(f"General follow-up to topic {topic_type}")
            # Default to medical info query for general follow-ups
            return {
                "intent": Intent.MEDICAL_INFO_QUERY.value,
                "confidence": 0.9,
                "entities": {"action": "followup", "topic": current_topic.get('name', 'general'),
                             "original_text": user_input, "context_type": "anaphora_resolution"}
            }

    # 2.6 Additional AI-based short query check for very short messages (<= 5 words)
    if len(original_message.split()) <= 5:
        logger.debug(f"Detected short query: {original_message}")
        # If we have a current topic, this is likely a follow-up
        if conversation_context and conversation_context.get('current_topic'):
            current_topic = conversation_context.get('current_topic', {})
            logger.debug(f"Short query with current topic: {current_topic}")
            
            # If the message is really short (1-2 words) and doesn't contain a question mark,
            # it's very likely a follow-up to the current topic
            if len(original_message.split()) <= 2 and '?' not in original_message:
                topic_type = current_topic.get('type', '')
                topic_name = current_topic.get('name', '')
                print(f"DEBUG-SHORT-QUERY-3: Very short query detected, treating as direct follow-up to {topic_type}")
                
                # Map to appropriate intent based on current topic
                if topic_type in ['lab_result', 'lab_results', 'lab_results_query']:
                    return {
                        "intent": Intent.LAB_RESULTS_QUERY.value,
                        "confidence": 0.95,
                        "entities": {"action": "followup", "topic": topic_name, "original_text": user_input, 
                                    "context_type": "short_query"}
                    }
                elif topic_type in ['symptom_report', 'symptoms']:
                    return {
                        "intent": Intent.SYMPTOM_REPORT.value,
                        "confidence": 0.95,
                        "entities": {"action": "followup", "topic": topic_name, "original_text": user_input, 
                                    "context_type": "short_query"}
                    }
                elif topic_type in ['medication', 'medications']:
                    return {
                        "intent": Intent.MEDICAL_INFO_QUERY.value,
                        "confidence": 0.95,
                        "entities": {"action": "followup", "topic": topic_name, "original_text": user_input, 
                                    "context_type": "short_query"}
                    }
        
        context_prompt = f"\nPrevious topic: {conversation_context['current_topic'].get('name')}" if conversation_context and conversation_context.get('current_topic') else ""
        cache_key = f"short_query::{original_message}{context_prompt}"
        if cache_key in FALLBACK_CACHE:
            logger.info("Using cached GPT fallback for short query.")
            return FALLBACK_CACHE[cache_key]
        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are analyzing if this short user message is a follow-up to a previous topic or "
                        "a standalone query. Return a JSON object:\n"
                        "{\n"
                        '  "is_followup": boolean,\n'
                        '  "confidence": float,\n'
                        '  "related_intent": "lab_results_query" or "show_appointments" or ...,\n'
                        '  "reasoning": "string"\n'
                        "}"
                    )},
                    {"role": "user", "content": f"Message: {user_input}{context_prompt}"}
                ],
                temperature=0.1
            )
            if isinstance(response, Coroutine):
                logger.debug("GPT response is a coroutine, forcing await.")
                response = await response
            analysis = json.loads(response.choices[0].message.content)
            if analysis.get('is_followup') is True and analysis.get('confidence', 0) > 0.7:
                related_intent = analysis.get('related_intent')
                if related_intent == 'lab_results_query':
                    result = {
                        "intent": Intent.LAB_RESULTS_QUERY.value,
                        "confidence": analysis['confidence'],
                        "entities": {"action": "followup", "topic": conversation_context.get('current_topic', {}).get('name', 'unknown'),
                                     "original_text": user_input, "context_type": "semantic_analysis"}
                    }
                    FALLBACK_CACHE[cache_key] = result
                    return result
                elif related_intent == 'show_appointments':
                    result = {
                        "intent": Intent.SHOW_APPOINTMENTS.value,
                        "confidence": analysis['confidence'],
                        "entities": {"action": "view", "original_text": user_input}
                    }
                    FALLBACK_CACHE[cache_key] = result
                    return result
        except Exception as e:
            logger.error(f"Error in AI-enhanced short query analysis: {e}")

    # 2.7 Lab Result Patterns
    if any(pattern.search(original_message) for pattern in COMPILED_LAB_RESULT_PATTERNS):
        logger.info("Regex detection: Lab result pattern matched.")
        return {
            "intent": Intent.LAB_RESULTS_QUERY.value,
            "confidence": 0.9,
            "entities": {"topic": original_message, "original_text": user_input}
        }
    if any(pattern.search(original_message) for pattern in COMPILED_ADDITIONAL_LAB_PATTERNS):
        if re.search(r"(?:show|get|view|see)\s+.*results.*", original_message):
            logger.info("Regex detection: Additional lab pattern matched for viewing results.")
            return {
                "intent": Intent.LAB_RESULTS.value,
                "confidence": 0.9,
                "entities": {"action": "view", "original_text": user_input}
            }
        else:
            logger.info("Regex detection: Additional lab pattern matched for querying results.")
            return {
                "intent": Intent.LAB_RESULTS_QUERY.value,
                "confidence": 0.9,
                "entities": {"action": "query", "topic": original_message, "original_text": user_input}
            }

    # 2.8 Screening Patterns - check for sleep questions first and redirect them
    # Check if message is about sleep (redirect to medical_info_query instead)
    sleep_pattern = re.compile(r'sleep|rest|tired|insomnia|how\s+much\s+sleep|hours\s+of\s+sleep', re.IGNORECASE)
    if sleep_pattern.search(original_message):
        logger.info("Sleep question detected, routing to medical_info_query.")
        return {
            "intent": Intent.MEDICAL_INFO_QUERY.value, 
            "confidence": 0.95,
            "entities": {"topic": "sleep health", "original_text": user_input}
        }
        
    # Only match screening patterns if they're truly about screening reminders
    if any(pattern.search(original_message) for pattern in COMPILED_SCREENING_PATTERNS):
        logger.info("Regex detection: Screening pattern matched.")
        return {
            "intent": Intent.SCREENING.value,
            "confidence": 0.9,
            "entities": {"action": "respond", "original_text": user_input}
        }

    # 2.9 Medical Record Patterns
    if any(pattern.search(original_message) for pattern in COMPILED_MEDICAL_RECORD_PATTERNS):
        logger.info("Regex detection: Medical record pattern matched.")
        return {
            "intent": Intent.MEDICAL_RECORD_QUERY.value,
            "confidence": 0.9,
            "entities": {"record_type": "full", "original_text": user_input}
        }

    # 2.10 Medical Info Patterns
    if any(pattern.search(original_message) for pattern in COMPILED_MEDICAL_INFO_PATTERNS):
        topic_cleaned = extract_medical_topic(original_message)
        logger.info("Regex detection: Medical info pattern matched.")
        return {
            "intent": Intent.MEDICAL_INFO_QUERY.value,
            "confidence": 0.85,
            "entities": {"topic": topic_cleaned, "original_text": user_input}
        }

    # 2.11 Mental Health Patterns
    if any(pattern.search(original_message) for pattern in COMPILED_MENTAL_HEALTH_PATTERNS):
        logger.info("Regex detection: Mental health pattern matched.")
        return {
            "intent": Intent.MENTAL_HEALTH_QUERY.value,
            "confidence": 0.9,
            "entities": {"topic": "mental_health", "original_text": user_input}
        }

    # 2.12 Condition Patterns
    if any(pattern.search(original_message) for pattern in COMPILED_CONDITION_PATTERNS):
        logger.info("Regex detection: Condition pattern matched.")
        return {
            "intent": Intent.CONDITION_QUERY.value,
            "confidence": 0.9,
            "entities": {"topic": "conditions", "original_text": user_input}
        }

    # 2.13 Capability Patterns
    if any(pattern.search(original_message) for pattern in COMPILED_CAPABILITY_PATTERNS):
        logger.info("Regex detection: Capability pattern matched.")
        return {
            "intent": Intent.CAPABILITIES.value,
            "confidence": 1.0,
            "entities": {"topic": "capabilities", "original_text": user_input}
        }

    # 2.14 Explanation Patterns
    if any(pattern.search(original_message) for pattern in COMPILED_EXPLANATION_PATTERNS):
        logger.info("Regex detection: Explanation pattern matched.")
        return {
            "intent": Intent.EXPLANATION_QUERY.value,
            "confidence": 1.0,
            "entities": {"topic": user_input, "original_text": user_input}
        }

    # --- 3. GPT Fallback ---
    # Add examples to the system prompt instead of as separate messages
    fallback_prompt = """
You are a powerful medical chatbot assistant. Classify the user's intent from this list:
- set_appointment
- show_appointments
- medical_record_query
- medical_info_query
- symptom_report
- issue_report
- lab_results
- lab_results_query
- capabilities
- explanation_query
- email_verification
- reset_context
- delete_context
- greeting
- condition_query
- mental_health_query
- screening
- unknown

IMPORTANT: Use 'issue_report' for any health issue query that describes a symptom, problem or condition the user is experiencing, especially when they're looking for advice on what to do.

Examples:
- "I've been having trouble sleeping" → issue_report
- "My back has been hurting for days" → issue_report
- "I have a persistent cough that won't go away" → issue_report
- "I'm experiencing ringing in my ears" → issue_report
- "My vision has been blurry" → issue_report

Here are more examples with their expected classifications:

User: "i want to set an appointment"
Expected response: {"intent": "set_appointment", "confidence": 0.95, "entities": {}}

User: "I need to schedule a check-up"
Expected response: {"intent": "set_appointment", "confidence": 0.95, "entities": {}}

User: "What are my upcoming appointments?"
Expected response: {"intent": "show_appointments", "confidence": 0.9, "entities": {}}

User: "What was my potassium level on my last lab test?"
Expected response: {"intent": "lab_results_query", "confidence": 0.85, "entities": {"test_name": "potassium"}}

User: "Can you show me my allergies?"
Expected response: {"intent": "medical_record_query", "confidence": 0.9, "entities": {"record_type": "allergies"}}

User: "hello"
Expected response: {"intent": "greeting", "confidence": 1.0, "entities": {}}

User: "I feel depressed and can't sleep"
Expected response: {"intent": "mental_health_query", "confidence": 0.9, "entities": {"topic": "mental_health"}}

User: "I want to see my lab results from last month"
Expected response: {"intent": "lab_results_query", "confidence": 0.9, "entities": {"action": "query"}}

User: "Let's delete context now"
Expected response: {"intent": "delete_context", "confidence": 1.0, "entities": {"action": "delete"}}

User: "I have a headache and a fever"
Expected response: {"intent": "symptom_report", "confidence": 0.95, "entities": {"symptom_category": "general"}}

User: "What screenings should I get?"
Expected response: {"intent": "screening", "confidence": 0.9, "entities": {"action": "recommend"}}

User: "I've been having trouble sleeping for a few weeks now"
Expected response: {"intent": "issue_report", "confidence": 0.95, "entities": {"symptom_description": "I've been having trouble sleeping for a few weeks now"}}

User: "My back has been hurting for days"
Expected response: {"intent": "issue_report", "confidence": 0.95, "entities": {"symptom_description": "My back has been hurting for days"}}

User: "Why do I need a colonoscopy?"
Expected response: {"intent": "explanation_query", "confidence": 0.95, "entities": {"topic": "colonoscopy"}}

User: "What can you help me with?"
Expected response: {"intent": "capabilities", "confidence": 1.0, "entities": {}}

Return strict JSON:
{
  "intent": "<one of the above>",
  "confidence": 0.95,
  "entities": { ... }
}
"""
    context_info = conversation_context if conversation_context else {}
    gpt_messages = [
        {"role": "system", "content": fallback_prompt},
        {"role": "user", "content": f"Utterance: {user_input}\nContext: {json.dumps(context_info)}\nLast Intent: {last_intent}"}
    ]
    cache_key = f"gpt_fallback::{original_message}::{json.dumps(context_info)}::{last_intent}"
    if cache_key in FALLBACK_CACHE:
        logger.info("Using cached GPT fallback response.")
        return FALLBACK_CACHE[cache_key]

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=gpt_messages,
            temperature=0.2,
            max_tokens=150
        )
        if isinstance(response, Coroutine):
            logger.debug("GPT response is a coroutine, forcing await.")
            response = await response
        if not response or not response.choices:
            logger.error("Empty response from OpenAI fallback.")
            return {"intent": Intent.UNKNOWN.value, "confidence": 0.1, "entities": {}, "original_text": user_input}
        response_content = response.choices[0].message.content
        logger.debug(f"GPT Fallback raw response: {response_content}")
        try:
            intent_data = json.loads(response_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT fallback response as JSON: {e}")
            return {"intent": Intent.UNKNOWN.value, "confidence": 0.1, "entities": {}, "original_text": user_input}
        if not isinstance(intent_data, dict) or not all(k in intent_data for k in ["intent", "confidence"]):
            logger.error(f"GPT fallback response is invalid: {intent_data}")
            return {"intent": Intent.UNKNOWN.value, "confidence": 0.1, "entities": {}, "original_text": user_input}
        try:
            recognized_intent = Intent(intent_data["intent"]).value
        except (ValueError, KeyError):
            logger.warning(f"Invalid intent in GPT fallback response: {intent_data.get('intent')}")
            recognized_intent = Intent.UNKNOWN.value
        result = {
            "intent": recognized_intent,
            "confidence": float(intent_data.get("confidence", 0.1)),
            "entities": intent_data.get("entities", {}),
            "original_text": user_input
        }
        FALLBACK_CACHE[cache_key] = result
        return result
    except Exception as e:
        logger.error(f"Unexpected error in GPT fallback: {e}", exc_info=True)
        return {"intent": Intent.UNKNOWN.value, "confidence": 0.1, "entities": {}, "original_text": user_input}

# ============================================
#   Symptom & Condition Analysis (async)
# ============================================
async def analyze_symptom_and_conditions_with_ai(
    patient_id: str,
    user_message: str,
    conversation_history: Optional[list] = None,
    current_topic: Optional[dict] = None
) -> str:
    """
    Analyze symptoms and conditions with advanced AI using FHIR data.
    Detects language, retrieves the patient resource, and returns a triage response.
    """
    try:
        fhir_client =  get_async_fhir_client()
        detected_lang = await language_service.detect_language(user_message)
        emergency_text = language_service.get_localized_message('emergency_text', detected_lang)
        disclaimer = language_service.get_localized_message('disclaimer', detected_lang)
        patient = await fhir_client.server.perform_request('GET', f"Patient/{patient_id}")

        SEVERITY_LEVELS = {
            'EMERGENCY': {
                'prefix': '🚨 EMERGENCY MEDICAL ATTENTION NEEDED',
                'action': 'Please call emergency services (e.g. 112) immediately or go to the nearest ER.',
                'followup': 'Do not delay seeking help.'
            },
            'URGENT': {
                'prefix': '⚠️ URGENT MEDICAL ATTENTION ADVISED',
                'action': 'Please seek urgent medical care or contact your healthcare provider right away.',
                'followup': 'If symptoms worsen, call emergency services.'
            },
            'MODERATE': {
                'prefix': '⚕️ MEDICAL ATTENTION RECOMMENDED',
                'action': 'Schedule an appointment with your provider soon.',
                'followup': 'Monitor symptoms and seek urgent care if they worsen.'
            },
            'LOW': {
                'prefix': 'ℹ️ GENERAL HEALTH ADVICE',
                'action': 'Monitor your symptoms and practice self-care at home.',
                'followup': 'Schedule a routine appointment if symptoms persist.'
            }
        }

        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a medical triage assistant focusing on patient safety. Always err on the side of caution. "
                    "Return structured JSON with severity and recommended steps."
                )},
                {"role": "user", "content": f"""
Analyze this health concern with severity:

Patient Message: {user_message}

Return JSON with:
{{
    "severity_level": "EMERGENCY|URGENT|MODERATE|LOW",
    "primary_symptoms": [list of main symptoms],
    "related_conditions": [possible related conditions],
    "immediate_actions": [actions to take],
    "reasoning": "brief explanation",
    "requires_emergency": boolean,
    "followup_recommendation": "specific followup advice"
}}
"""}
            ],
            temperature=0.3,
            max_tokens=500
        )
        analysis = json.loads(response.choices[0].message.content)
        severity = analysis.get('severity_level', 'MODERATE')
        severity_info = SEVERITY_LEVELS.get(severity, SEVERITY_LEVELS['MODERATE'])
        primary_symptoms = analysis.get('primary_symptoms', [])
        symptom_list = ", ".join(primary_symptoms) if primary_symptoms else "None"
        response_text = [
            f"{severity_info['prefix']}",
            "",
            f"Symptoms identified: {symptom_list}",
            "",
            f"RECOMMENDATION: {severity_info['action']}",
            "",
            f"Important: {severity_info['followup']}"
        ]
        if analysis.get('requires_emergency', False):
            response_text.append("\n🚨 EMERGENCY NUMBERS:")
            response_text.append("General Emergency: 112 (Europe), 911 (US), or local equivalent.")
            response_text.append("If in doubt, call emergency services immediately.")
        if disclaimer:
            response_text.append(f"\n{disclaimer}")
        else:
            response_text.append("\nPlease note this does not replace professional medical advice.")
        return "\n".join(response_text)
    except Exception as e:
        logger.error(f"Error in symptom analysis: {str(e)}", exc_info=True)
        return (
            "For your safety, please seek medical attention or contact emergency services "
            "if you're concerned about any symptoms."
        )
logger.debug("Intent service initialization complete")