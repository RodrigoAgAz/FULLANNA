# chatbot/views/handlers/chat_handler.py

import inspect
import logging
import json
import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from asgiref.sync import sync_to_async
# Django imports
from django.conf import settings
from django.http import JsonResponse
# Third-party imports
from openai import AsyncOpenAI
from twilio.rest import Client
from chatbot.views.services.fhir_service import FHIRService
from fhirclient.models.observation import Observation
from fhirclient.models.diagnosticreport import DiagnosticReport
from chatbot.views.config import config as app_config
from chatbot.views.services.language_service import LanguageService, LanguageHandler
from chatbot.views.services.session import update_session
from chatbot.views.utils.datetime_utils import format_datetime_for_user
from chatbot.views.utils.shared import get_resource_name
from chatbot.views.utils.constants import OPENAI_MODEL
import dateparser
from chatbot.views.services.intent_service import (
    detect_intent,
)
from chatbot.views.services.symptom_guidance_service import SymptomGuidanceService
from chatbot.views.handlers.symptom_guidance_handler import SymptomGuidanceHandler
from chatbot.views.services.personalized_medical_advice_service import (
    PersonalizedMedicalAdviceService,
    AsyncGPT4Client
)
from chatbot.views.handlers.medical_handler import (
    get_complete_medical_record,
)
from chatbot.views.services.fhir_service import (
    get_available_practitioners,
)
from chatbot.views.services.scheduler import search_available_slots, get_patient_appointments

from fhirclient.models.condition import Condition
from fhirclient.models.patient import Patient
from fhirclient.models.immunization import Immunization
from fhirclient.models.bundle import Bundle
from fhirclient.server import FHIRServer
from .debug_utils import trace_async_calls, debug_intent_handlers

from .context_manager import ContextManager  # Import the ContextManager

logger = logging.getLogger(__name__)

MEDICAL_DISCLAIMER = """
This information is for educational purposes only and is not a substitute for professional medical advice.
Always seek the advice of your physician or other qualified health provider with any questions you may have.
"""
print("11")
@trace_async_calls
class ChatHandler:
    def __init__(self, session_data, user_message, user_id=None):
        # If no user_id is provided, default to the phone number in the session
        self.user_id = user_id if user_id is not None else session_data.get('phone_number')
        self.session = session_data
        self.user_message = user_message

        # Log the user_id for debugging purposes
        logger.debug(f"ChatHandler initialized for user_id: {self.user_id}")

        # Initialize FHIR service using your existing FHIRService class
        self.fhir_service = FHIRService()
        self.fhir_client = self.fhir_service  # Use fhir_service for all FHIR operations

        # Extract patient data from session if available
        self.patient = session_data.get('patient')
        if self.patient and isinstance(self.patient, dict):
            # Prefer numeric_id if available; otherwise, use 'id' or a resource ID from the patient data
            if 'numeric_id' in self.patient:
                self.patient_id = self.patient['numeric_id']
                logger.debug(f"Using numeric patient ID: {self.patient_id}")
            elif 'id' in self.patient:
                self.patient_id = self.patient['id']
                logger.debug(f"Using full patient ID: {self.patient_id}")
            elif 'resource' in self.patient and isinstance(self.patient['resource'], dict):
                self.patient_id = self.patient['resource'].get('id')
                logger.debug(f"Using resource patient ID: {self.patient_id}")
            else:
                self.patient_id = None
                logger.warning("No valid patient ID found in patient data")
        else:
            self.patient_id = None
            logger.debug("No patient data in session")

        # Initialize other attributes and clients
        self.current_context = session_data.get('current_context')
        self.last_intent = session_data.get('last_intent')
        self.conversation_history = session_data.get('conversation_history', [])
        if session_data and 'conversation_context' in session_data:
            self.conversation_context.__dict__.update(session_data['conversation_context'])

        try:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.language_handler = LanguageHandler()
            self.language_service = LanguageService()
        except Exception as e:
            logger.error(f"Error initializing clients: {str(e)}", exc_info=True)
            raise RuntimeError("Failed to initialize required clients")

        # Register intent handlers.  This is the CRITICAL part.
        self.intent_handlers = {
            'medical_info_query': self._handle_symptom_report,
            'medical_record': self._handle_medical_record,
            'symptoms': self._handle_symptom_report,  # This handles all symptom queries
 
            'set_appointment': self.handle_booking_flow,
            'appointment': self.handle_booking_flow,
            'show_appointments': self._handle_show_appointments,
            'nextAppointment': self._handle_show_appointments,
            'query_appointments': self._handle_show_appointments,
            'immunizations': self._handle_immunizations_query,
            'vaccines': self._handle_immunizations_query,
            'lab_results': self._handle_lab_results,
            'lab_results_query': self._handle_lab_results,
            'capabilities': self._handle_capabilities_query,
            'explanation_query': self._handle_explanation_query,
            'reset_context': self._handle_reset_context,
            'greeting': self._handle_greeting,
            'conditions': self.handle_conditions_query,
            'medications': self.handle_medications_query,
            'screening': self._handle_screening,
            'height': self._handle_height_query
        }

        # Initialize lab context and context manager as before
        self.lab_context = {
            'last_results': None,
            'current_topic': None
        }
        self.context_manager = ContextManager(user_id=self.user_id, session=self.session, openai_client=self.openai_client) #correct way of calling

    async def initialize(self):
        """Async initialization tasks"""
        print("DEBUG-CH-INIT-1: ChatHandler initialize started")
        logger.debug("[initialize] ChatHandler initialize started")
        try:
            print("DEBUG-CH-INIT-2: About to detect language")
            self.current_language = await self.language_service.detect_language(self.user_message)
            print(f"DEBUG-CH-INIT-3: Language detected: {self.current_language}")
            # Don't return self, just complete initialization
            print("DEBUG-CH-INIT-4: Initialize completed successfully")
            return
        except Exception as e:
            print(f"DEBUG-CH-INIT-ERROR: Error in async initialization: {str(e)}")
            import traceback
            print(f"DEBUG-CH-INIT-ERROR-TRACE: {traceback.format_exc()}")
            logger.error(f"Error in async initialization: {str(e)}")
            raise
        finally:
            print("DEBUG-CH-INIT-5: Initialization finished (finally block)")
            logger.debug("(initialisation finished)")

    async def handle_message(self, message=None, **kwargs):
        """Main message handling method, now with extensive debugging."""
        print("DEBUG-CH-HM-1: Starting handle_message")
        logger.debug("=== ENTER handle_message ===")
        
        if message is None:
            print("DEBUG-CH-HM-2: No message provided, using self.user_message")
            message = self.user_message
        print(f"DEBUG-CH-HM-3: Processing message: {message}")
        logger.debug(f"Processing message: {message}")

        try:
            # Language Detection and Translation
            print("DEBUG-CH-HM-4: About to perform language detection")
            logger.debug("Performing language detection")
            print("DEBUG-CH-HM-5: Calling language_service.detect_language")
            detected_lang = await self.language_service.detect_language(self.user_message)
            print(f"DEBUG-CH-HM-6: Language detected: {detected_lang}")
            
            if detected_lang != 'en':
                print(f"DEBUG-CH-HM-7: Skipping translation (disabled)")
                logger.debug(f"Skipping translation from {detected_lang} to English")
                # Skip translation and just use the original text
                english_text = self.user_message
                needs_translation = False
            else:
                print("DEBUG-CH-HM-10: No translation needed (English detected)")
                english_text = self.user_message
                needs_translation = False
            print(f"DEBUG-CH-HM-11: Text for processing: {english_text}")
            logger.debug(f"Text for processing: {english_text}")

            # Context management
            print("DEBUG-CH-HM-12: Starting context management")
            logger.debug("Adding message to context manager")
            try:
                print("DEBUG-CH-HM-13: Calling context_manager.add_message")
                await self.context_manager.add_message(self.user_id, self.user_message)
                print("DEBUG-CH-HM-14: Message added to context manager")
            except Exception as cm_error:
                print(f"DEBUG-CH-HM-ERROR: Error adding message to context manager: {str(cm_error)}")
                import traceback
                print(f"DEBUG-CH-HM-ERROR-TRACE: {traceback.format_exc()}")

            try:
                print("DEBUG-CH-HM-15: Getting context")
                context = await self.context_manager.get_context(self.user_id)
                print("DEBUG-CH-HM-16: Context retrieved")
                
                print("DEBUG-CH-HM-17: Getting user facts")
                user_facts = await self.context_manager.get_user_facts(self.user_id)
                print("DEBUG-CH-HM-18: User facts retrieved")
                
                print("DEBUG-CH-HM-19: Extracting user facts from message")
                new_facts = await self.context_manager._extract_user_facts(self.user_message)
                print(f"DEBUG-CH-HM-20: User facts extracted: {new_facts}")
            
            except Exception as facts_error:
                print(f"DEBUG-CH-HM-ERROR: Error in facts extraction: {str(facts_error)}")
                import traceback
                print(f"DEBUG-CH-HM-ERROR-TRACE: {traceback.format_exc()}")
                # Set defaults if there's an error
                context = {"summary": "", "recent_messages": []}
                user_facts = {}
                new_facts = {}

            if new_facts:
                print("DEBUG-CH-HM-21: Adding new facts to session")
                logger.debug(f"Found new facts: {new_facts}")
                if 'user_facts' not in self.session:
                    self.session['user_facts'] = {}
                # Merge them
                for k, v in new_facts.items():
                    self.session['user_facts'][k] = v
                print("DEBUG-CH-HM-22: Updating session with new facts")
                await update_session(self.user_id, self.session)
                print("DEBUG-CH-HM-23: Session updated")

            # Prepare the context for intent detection
            print("DEBUG-CH-HM-24: Preparing context for intent detection")
            context_info = {
                "summary": context["summary"],
                "recent_messages": context["recent_messages"],
                "user_facts": user_facts
            }
            print(f"DEBUG-CH-HM-25: Context info prepared: {context_info}")

            # --- Intent Detection ---
            print("DEBUG-CH-HM-26: Starting intent detection")
            logger.debug("Detecting intent")
            try:
                print("DEBUG-CH-HM-27: Calling detect_intent")
                intent_data = await detect_intent(
                    user_input=english_text,
                    conversation_context=context_info,
                    last_intent=self.session.get('last_intent')
                )
                print(f"DEBUG-CH-HM-28: Intent detected: {intent_data.get('intent')}")
            except Exception as intent_error:
                print(f"DEBUG-CH-HM-ERROR: Error in intent detection: {str(intent_error)}")
                import traceback
                print(f"DEBUG-CH-HM-ERROR-TRACE: {traceback.format_exc()}")
                # Provide default intent data if there's an error
                intent_data = {"intent": "unknown", "confidence": 0.0, "entities": {}}
            logger.debug(f"Detected intent: {intent_data.get('intent')}, confidence: {intent_data.get('confidence')}")
            logger.debug(f"[handle_message] Detected intent data: {json.dumps(intent_data, indent=2)}")

            # Extract intent information
            intent = intent_data.get("intent")
            confidence = intent_data.get("confidence", 0.0)
            entities = intent_data.get("entities", {})

            responses = []

            # Check for active booking flow or booking-related intent
            if self.session.get('booking_state'):
                logger.debug("Processing active booking flow")
                # Check for cancel command first
                if english_text.lower() == 'cancel':
                    logger.debug("Cancelling booking")
                    self.session.pop('booking_state', None)
                    await update_session(self.user_id, self.session)
                    return ["Booking cancelled. I'm here to help you with any questions you may have."], self.session
                
                # Continue with booking flow if not cancelled
                logger.debug("[handle_message] Handling booking flow")
                response, self.session = await self.handle_booking_flow(self.user_message)
                logger.debug(f"Booking flow returned response type: {type(response).__name__}")
                print(f"DEBUG: Type of response in handle_message after booking flow: {type(response)}")
                
                # Check for unawaited coroutine
                if inspect.iscoroutine(response):
                    logger.error(f"CRITICAL ERROR: Got unawaited coroutine {response}")
                    logger.error(f"Attempting to await the coroutine")
                    response = await response  # Try to fix it
                
                print(f"Final response type: {type(response)}")
                print(f"Is coroutine: {inspect.iscoroutine(response)}")
                
                return response, self.session

            elif intent == "set_appointment":
                logger.debug("Processing set_appointment intent")
                # Check if this is a rescheduling request
                if any(word in english_text.lower() for word in ["reschedule", "change", "move", "modify"]):
                    logger.debug("[handle_message] Detected rescheduling request")
                    response, self.session = await self._handle_reschedule_request()
                    
                    # Check for unawaited coroutine
                    if inspect.iscoroutine(response):
                        logger.error(f"CRITICAL ERROR: Got unawaited coroutine {response}")
                        logger.error(f"Attempting to await the coroutine")
                        response = await response  # Try to fix it
                    
                    return response, self.session

                # Start new booking flow if it's a fresh appointment request
                logger.debug("[handle_message] Starting new booking flow")
                response, self.session = await self.handle_booking_flow(self.user_message)
                print(f"DEBUG: Type of response in handle_message after booking flow: {type(response)}")
                
                # Check for unawaited coroutine
                if inspect.iscoroutine(response):
                    logger.error(f"CRITICAL ERROR: Got unawaited coroutine {response}")
                    logger.error(f"Attempting to await the coroutine")
                    response = await response  # Try to fix it
                
                return response, self.session

            # Store the intent data in the instance
            self.intent_data = intent_data

            # Add condition-specific routing
            if any(keyword in self.user_message.lower() for keyword in
                ['my conditions', 'my medical conditions', 'what conditions', 'show me my conditions']):
                logger.debug("Handling conditions query")
                response, self.session = await self._handle_explanation_query(self.user_message)
                
                # Check for unawaited coroutine
                if inspect.iscoroutine(response):
                    logger.error(f"CRITICAL ERROR: Got unawaited coroutine {response}")
                    logger.error(f"Attempting to await the coroutine")
                    response = await response  # Try to fix it
                
                return response, self.session

            # Continue with intent handling regardless of triage classification
            if not intent:
                logger.debug("[handle_message] No intent detected")
                general_response = "I'm not sure how to help with that. Could you please rephrase?"
                if needs_translation:
                    general_response = await self.language_handler.translate_text(general_response, self.current_language)
                responses.append(general_response)
            else:
                primary_intent = intent
                logger.debug(f"[handle_message] Primary intent: {primary_intent}")
                logger.debug(f"Available handlers: {self.intent_handlers.keys()}")
                logger.debug(f"Looking for handler: {primary_intent}")
                logger.debug(f"[handle_message] Handler dict: {self.intent_handlers}")
                logger.debug(f"[handle_message] Handler type: {type(self.intent_handlers.get(primary_intent))}")

                # Add capabilities to your intent handling
                if primary_intent == 'capabilities':
                    logger.debug("Handling capabilities intent")
                    response, self.session = await self._handle_capabilities_query()
                    
                    # Check for unawaited coroutine
                    if inspect.iscoroutine(response):
                        logger.error(f"CRITICAL ERROR: Got unawaited coroutine {response}")
                        logger.error(f"Attempting to await the coroutine")
                        response = await response  # Try to fix it
                    
                    return response, self.session

                # Special handling for viewing appointments
                if primary_intent == 'appointment' and any(keyword in self.user_message.lower()
                    for keyword in ['show', 'view', 'my', 'upcoming']):
                    logger.debug("[handle_message] Handling show appointments request")
                    appointments_response, self.session = await self._handle_show_appointments()
                    
                    # Check for unawaited coroutine
                    if inspect.iscoroutine(appointments_response):
                        logger.error(f"CRITICAL ERROR: Got unawaited coroutine {appointments_response}")
                        logger.error(f"Attempting to await the coroutine")
                        appointments_response = await appointments_response  # Try to fix it
                    
                    return appointments_response, self.session

                # Special handling for appointment booking initialization
                elif primary_intent == 'appointment' and not self.session.get('booking_state'):
                    logger.debug("[handle_message] Initializing new appointment booking")
                    self.session['booking_state'] = {
                        'step': 'select_practitioner_type',
                        'appointment_info': {}
                    }
                    await self._update_session()
                    
                    messages = [
                        "What type of healthcare provider would you like to see?\n\n"
                        "1. Doctor\n"
                        "2. Nurse\n"
                        "3. Specialist\n\n"
                        "Please select a number or type 'cancel' to stop booking."
                    ]
                    if needs_translation:
                        messages = [await self.language_handler.translate_text(m, self.current_language) for m in messages]
                    responses.extend(messages)
                    
                else:
                    # Intent handlers mapping with async/sync specifications
                    intent_handlers = {
                        # Async handlers
                        'medical_record': self._handle_medical_record,
                        'medical_info_query': self._handle_symptom_report,
                        'medical_info': self._handle_medical_record,
                        'show_records': self._handle_medical_record,
                        'set_appointment': self.handle_booking_flow,
                        'appointment': self.handle_booking_flow,
                        'nextAppointment': self._handle_show_appointments,
                        'query_appointments': self._handle_show_appointments,
                        'show_appointments': self._handle_show_appointments,
                        'immunizations': self._handle_immunizations_query,
                        'vaccines': self._handle_immunizations_query,
                        'lab_results': self._handle_lab_results,
                        # Regular handlers requiring user_id
                        'height': self._handle_height_query,
                        'greeting': self._handle_greeting,
                        'conditions': self.handle_conditions_query,
                        'medications': self.handle_medications_query,
                        'capabilities': self._handle_capabilities_query,
                        'explanation_query': self._handle_explanation_query,
                    }

                    # Get the handler from the instance's intent_handlers
                    logger.debug(f"Looking for handler for intent: {primary_intent}")
                    handler = self.intent_handlers.get(primary_intent)
                    logger.debug(f"Found handler: {handler.__name__ if handler else 'None'}")

                    if handler:
                        try:
                            logger.debug(f"Calling handler with message={message}, intent_data={intent_data}")
                            response = await handler(message=message, intent_data=intent_data)
                            logger.debug(f"Handler returned response of type: {type(response).__name__}")
                            
                            # Check for unawaited coroutine
                            if inspect.iscoroutine(response):
                                logger.error(f"CRITICAL ERROR: Got unawaited coroutine {response}")
                                logger.error(f"Attempting to await the coroutine")
                                response = await response  # Try to fix it
                            
                            print(f"Final response type: {type(response)}")
                            print(f"Is coroutine: {inspect.iscoroutine(response)}")
                            
                            # If returning a tuple, check each part
                            if isinstance(response, tuple):
                                # Create a new tuple with awaited items if needed
                                new_response = []
                                for i, item in enumerate(response):
                                    if inspect.iscoroutine(item):
                                        logger.error(f"Tuple item {i} is a coroutine!")
                                        new_response.append(await item)  # Await the coroutine
                                    else:
                                        new_response.append(item)
                                response = tuple(new_response)  # Create a new tuple
                                
                                logger.debug(f"Response is a tuple with {len(response)} items")
                                return response
                            else:
                                logger.debug("Response is not a tuple, wrapping with session")
                                return response, self.session
                        except Exception as e:
                            logger.error(f"[handle_message] Error in handler execution: {str(e)}")
                            raise
                    else:
                        logger.warning(f"[handle_message] No handler found for intent: {primary_intent}")
                        unknown_intent_response = "I'm not sure how to help with that specific request. Could you try rephrasing?"
                        if needs_translation:
                            unknown_intent_response = await self.language_handler.translate_text(
                                unknown_intent_response,
                                self.current_language
                            )
                        responses.append(unknown_intent_response)

            # Create JsonResponse at the end
            print(f"DEBUG-CH-HM-FINAL-1: Creating final JsonResponse with {len(responses)} messages")
            logger.debug(f"Creating final JsonResponse with {len(responses)} messages")
            
            # Final check for coroutines
            if inspect.iscoroutine(responses):
                print(f"DEBUG-CH-HM-FINAL-ERROR: Got unawaited coroutine {responses}")
                logger.error(f"CRITICAL ERROR: Got unawaited coroutine {responses}")
                logger.error(f"Attempting to await the coroutine")
                print(f"DEBUG-CH-HM-FINAL-2: Attempting to await the coroutine")
                responses = await responses  # Try to fix it
                print(f"DEBUG-CH-HM-FINAL-3: Successfully awaited coroutine")
            
            print(f"DEBUG-CH-HM-FINAL-4: Final response type: {type(responses)}")
            print(f"DEBUG-CH-HM-FINAL-5: Is coroutine: {inspect.iscoroutine(responses)}")
            
            # Create the response object
            final_response = JsonResponse({"messages": responses})
            print(f"DEBUG-CH-HM-FINAL-6: Created JsonResponse object: {type(final_response)}")
            print(f"DEBUG-CH-HM-FINAL-7: Is JsonResponse a coroutine? {inspect.iscoroutine(final_response)}")
            
            # Create the return tuple
            return_value = (final_response, self.session)
            print(f"DEBUG-CH-HM-FINAL-8: Return value created: {type(return_value)}")
            print(f"DEBUG-CH-HM-FINAL-9: Is return value a coroutine? {inspect.iscoroutine(return_value)}")
            
            # Return the tuple with response and session
            return return_value

        except Exception as e:
            print(f"DEBUG-CH-HM-ERROR-FINAL: Error in handle_message: {str(e)}")
            import traceback
            print(f"DEBUG-CH-HM-ERROR-FINAL-TRACE: {traceback.format_exc()}")
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            
            error_response = JsonResponse({
                "messages": ["I'm sorry, something went wrong while processing your request."]
            })
            print(f"DEBUG-CH-HM-ERROR-FINAL-1: Created error JsonResponse: {type(error_response)}")
            print(f"DEBUG-CH-HM-ERROR-FINAL-2: Is error response a coroutine? {inspect.iscoroutine(error_response)}")
            
            return_tuple = (error_response, self.session)
            print(f"DEBUG-CH-HM-ERROR-FINAL-3: Created error return tuple: {type(return_tuple)}")
            print(f"DEBUG-CH-HM-ERROR-FINAL-4: Is error return tuple a coroutine? {inspect.iscoroutine(return_tuple)}")
            
            return return_tuple

        finally:
            # Store conversation_history and user_facts back to session
            try:
                print("DEBUG-CH-HM-FINALLY-1: Saving conversation history and user facts to session")
                logger.debug("[handle_message] Saving conversation history and user facts to session")
                await self.context_manager.save_session()
                print("DEBUG-CH-HM-FINALLY-2: Session saved successfully")
            except Exception as session_error:
                print(f"DEBUG-CH-HM-FINALLY-ERROR: Failed to save session: {str(session_error)}")
                import traceback
                print(f"DEBUG-CH-HM-FINALLY-ERROR-TRACE: {traceback.format_exc()}")
                logger.error(f"[handle_message] Failed to save session: {str(session_error)}", exc_info=True)
            print("DEBUG-CH-HM-FINALLY-3: Exiting handle_message")
            logger.debug("=== EXIT handle_message ===")

    async def _detect_conversation_topic(self, message):
        """Detect the topic of conversation from message and history"""
        topic_categories = {
            'respiratory': ['asthma', 'bronchitis', 'breathing', 'lung', 'respiratory'],
            'musculoskeletal': ['elbow', 'arm', 'shoulder', 'knee', 'leg', 'back'],
            'allergies': ['hayfever', 'allergic', 'allergy'],
            'symptoms': ['pain', 'hurt', 'ache', 'sore']
        }

        message_words = message.lower().split()
        current_topics = set()

        # Check current message for topics
        for category, keywords in topic_categories.items():
            if any(keyword in message_words for keyword in keywords):
                current_topics.add(category)

        # Check recent history if no topic in current message
        if not current_topics and self.conversation_history:
            recent_messages = [msg['message'].lower() for msg in self.conversation_history[-3:]]
            for msg in recent_messages:
                for category, keywords in topic_categories.items():
                    if any(keyword in msg for keyword in keywords):
                        current_topics.add(category)

        return list(current_topics) if current_topics else None
   

    async def handle_booking_flow(self, message=None, intent_data=None) -> JsonResponse:
        """Handle the booking flow state machine"""
        try:
            # Check if we're in an active booking flow
            booking_state = self.session.get('booking_state', {})

            # If we have an active booking state, handle the current step
            if booking_state and booking_state.get('step'):
                logger.debug(f"Continuing booking flow at step: {booking_state['step']}")
                step_handlers = {
                    'initial_choice': self._handle_initial_choice,
                    'select_role': self._handle_type_selection,
                    'select_practitioner': self._handle_practitioner_selection,
                    'enter_reason': self._handle_reason_entry,
                    'select_datetime': self._handle_datetime_selection,
                    'confirm_booking': self._handle_booking_confirmation
                }

                handler = step_handlers.get(booking_state['step'])
                if handler:
                    response = await handler(booking_state)
                    print(f"DEBUG: Type of response in handle_booking_flow after {booking_state['step']}: {type(response)}")  
                    return response
                else:
                    logger.error(f"Invalid booking step: {booking_state['step']}")
                    return await self._handle_booking_error("Invalid booking state")

            # Initialize new booking flow
            logger.debug("Initializing new booking flow")
            # Get available practitioners using FHIRService
            practitioners = await self.fhir_service.get_available_practitioners()

            if not practitioners:
                return JsonResponse({
                    "messages": ["I apologize, but no healthcare providers are currently available."]
                })

            # Initialize booking state
            self.session['booking_state'] = {
                'step': 'initial_choice',
                'appointment_info': {}
            }
            await update_session(self.user_id, self.session)

            response = JsonResponse({
                "messages": [
                    "How would you like to find a healthcare provider?\n\n"
                    "1. Search by practitioner name\n"
                    "2. Search by role (Doctor, Nurse, Specialist)\n\n"
                    "Or type 'cancel' to stop booking."
                ]
            })
            print(f"DEBUG: Type of response in handle_booking_flow before return: {type(response)}")  
            return response

        except Exception as e:
            logger.error(f"Error in booking flow: {str(e)}", exc_info=True)
            return await self._handle_booking_error("Error processing booking request")

    async def _handle_datetime_selection(self, booking_state):
        """
        Handle the datetime selection for appointment booking.
        This version tries multiple approaches:
        1. Direct parsing with Python's dateparser.
        2. If direct parsing fails, tries a GPT-based approach (optional).
        3. Provides clear error messages to the user.
        """
        user_input = self.user_message.lower().strip()

        # Allow the user to cancel
        if user_input == 'cancel':
            self.session.pop('booking_state', None)
            await self._update_session()
            return JsonResponse({
                "messages": ["Booking cancelled. Is there anything else I can help you with?"]
            }), self.session

        # Attempt to parse using dateparser for maximum flexibility
        parsed_datetime, error_message = await self._parse_datetime_with_timezone(user_input)
        if error_message:
            # If parsing failed, give feedback and re-ask
            return JsonResponse({"messages": [error_message]})

        # If parsed correctly, continue with slot checking
        logger.debug(f"Looking for slot at time: {parsed_datetime.isoformat()}")
        try:
            search_time = parsed_datetime.strftime("%Y-%m-%dT%H:%M:00+00:00")
            logger.debug(f"Searching for slot with time: {search_time}")

            # Search for an available slot in FHIR
            search_params = {
                'schedule': f"Schedule/{booking_state.get('schedule', '25549')}",
                'start': f"eq{search_time}",
                'status': 'free'
            }
            logger.debug(f"Search params: {search_params}")

            slots = await self.fhir_service.search("Slot", search_params)
            if not slots or 'entry' not in slots or not slots['entry']:
                return JsonResponse({
                    "messages": ["That time slot is not available. Please select another time."]
                }), self.session

            # Get the first available slot
            selected_slot = slots['entry'][0]['resource']

            # Store the slot information
            booking_state['appointment_info'].update({
                'datetime': parsed_datetime.isoformat(),
                'slot': {
                    'id': selected_slot['id'],
                    'start': selected_slot['start'],
                    'end': selected_slot['end']
                }
            })

            # Move to confirmation step
            booking_state['step'] = 'confirm_booking'
            self.session['booking_state'] = booking_state
            await self._update_session()
            formatted_time = await self._format_appointment_time(selected_slot['start'])
            return JsonResponse({
                "messages": [
                    f"Please confirm your appointment:\n\n"
                    f"Provider: {booking_state['appointment_info'].get('practitioner_name')}\n"
                    f"Type: {booking_state['appointment_info']['type'].title()}\n"
                    f"Time: {formatted_time}\n"
                    f"Reason: {booking_state['appointment_info'].get('reason', 'General consultation')}\n\n"
                    "Type 'confirm' to book or 'cancel' to start over."
                ]
            }), self.session

        except Exception as e:
            logger.error(f"Error searching for slots: {str(e)}", exc_info=True)
            return await self._handle_booking_error("Error checking slot availability")

    async def _handle_practitioner_selection(self, booking_state):
        try:
            if self.user_message.lower() == 'cancel':
                self.session.pop('booking_state', None)
                await update_session(self.user_id, self.session)
                return JsonResponse({
                    "messages": ["Booking cancelled. Is there anything else I can help you with?"]
                }), self.session

            if not self.user_message.isdigit():
                return JsonResponse({
                    "messages": ["Please select a practitioner by entering their number, or type 'cancel' to stop booking."]
                }), self.session

            selection = int(self.user_message)
            practitioners = self.session['booking_state'].get('practitioners', {})

            if not practitioners:
                logger.error("No practitioners dictionary in booking state")
                return self._handle_booking_error()

            if str(selection) not in practitioners:
                return JsonResponse({
                    "messages": ["Please select a valid practitioner number from the list."]
                }), self.session

            practitioner_id = practitioners[str(selection)]

            # Use the async search method instead of sync read
            search_result = await self.fhir_service.search('Practitioner', {'_id': practitioner_id})
            practitioner = search_result['entry'][0]['resource'] if search_result.get('entry') else None

            if not practitioner:
                logger.error(f"Could not fetch practitioner with ID {practitioner_id}")
                return self._handle_booking_error()

            # Update booking state
            self.session['booking_state']['selected_practitioner'] = practitioner_id
            self.session['booking_state']['appointment_info']['practitioner_name'] = get_resource_name(practitioner)
            self.session['booking_state']['step'] = 'enter_reason'  # Changed from 'confirm_booking' to 'enter_reason'
            await update_session(self.user_id, self.session)

            return JsonResponse({
                "messages": [
                    f"You've selected {self.session['booking_state']['appointment_info']['practitioner_name']}.\n\n"
                    "Please enter the reason for your visit."
                ]
            }), self.session

        except Exception as e:
            logger.error(f"Error in practitioner selection: {str(e)}", exc_info=True)
            return self._handle_booking_error()

    async def _handle_booking_error(self):
        """Handle booking flow errors uniformly"""
        self.session.pop('booking_state', None)
        return JsonResponse({
            "messages": ["I'm sorry, there was an error processing your booking request. Please try again."]
        }), self.session

    async def _handle_booking_confirmation(self, booking_state):
        """Handle final booking confirmation"""
        try:
            if self.user_message.lower() not in ['confirm', 'yes', 'y']:
                return JsonResponse({
                    "messages": ["Please type 'confirm' to book the appointment or 'cancel' to start over."]
                }), self.session

            # Get complete slot info from booking state
            slot_info = booking_state.get('appointment_info', {}).get('slot')
            if not slot_info or not all(key in slot_info for key in ['id', 'start', 'end']):
                logger.error(f"Invalid slot information in booking state: {booking_state}")
                return self._handle_booking_error()

            # Create appointment resource
            appointment_data = {
                'resourceType': 'Appointment',
                'status': 'booked',
                'slot': [{'reference': f"Slot/{slot_info['id']}"}],
                'start': slot_info['start'],
                'end': slot_info['end'],
                'participant': [
                    {
                        'actor': {'reference': f"Patient/{self.patient_id}"},
                        'status': 'accepted'
                    },
                    {
                        'actor': {'reference': f"Practitioner/{booking_state['selected_practitioner']}"},
                        'status': 'accepted'
                    }
                ],
                'appointmentType': {
                    'text': booking_state['appointment_info']['type']
                },
                'reason': [{
                    'text': booking_state['appointment_info'].get('reason', 'General consultation')
                }],
                'created': datetime.now(ZoneInfo("UTC")).isoformat()
            }

            # Create the appointment
            created = await sync_to_async(self.fhir_client.create)('Appointment', appointment_data)
            if not created:
                return self._handle_booking_error()

            # Update slot status
            slot_update = {
                'resourceType': 'Slot',
                'id': slot_info['id'],
                'status': 'busy'
            }
            await sync_to_async(self.fhir_client.update)('Slot', slot_info['id'], slot_update)

            # Clear booking state
            self.session.pop('booking_state', None)
            await update_session(self.user_id, self.session)

            # Format success message
            formatted_time = await self._format_appointment_time(slot_info['start'])
            return JsonResponse({
                "messages": [
                    f"Your appointment has been confirmed!\n\n"
                    f"Provider: {booking_state['appointment_info']['practitioner_name']}\n"
                    f"Type: {booking_state['appointment_info']['type'].title()}\n"
                    f"Time: {formatted_time}\n"
                    f"Reason: {booking_state['appointment_info'].get('reason', 'General consultation')}\n\n"
                    f"You will receive a confirmation email shortly. Is there anything else I can help you with?"
                ]
            }), self.session

        except Exception as e:
            logger.error(f"Error in booking confirmation: {str(e)}")
            return self._handle_booking_error()
    
    async def _handle_symptom_report(self, message=None, intent_data=None):
        """
        Simplified symptom handler that directly uses SymptomGuidanceService
        to analyze symptoms and provide appropriate guidance.
        """
        try:
            if message is None:
                message = self.user_message
                
            logger.debug(f"Processing symptom query: {message}")
            
            # Initialize the symptom guidance service directly
            symptom_service = SymptomGuidanceService()
            
            # Get patient data from session if available
            patient_data = self.patient.get('resource') if self.patient else None
            
            # 1. Check for red flags first
            has_red_flags, red_flags = await sync_to_async(symptom_service.red_flag_checker)(message)
            
            # 2. Analyze symptoms
            symptom_analysis = await sync_to_async(symptom_service.symptom_analyzer)(
                message, 
                patient_data
            )
            
            # 3. Determine risk level
            risk_assessment = await sync_to_async(symptom_service.risk_level_determiner)(
                symptom_analysis,
                red_flags if has_red_flags else None
            )
            
            # 4. Format response
            response_data = await sync_to_async(symptom_service.response_formatter)(
                risk_assessment,
                patient_data
            )
            
            # 5. Get specific guidance based on symptoms 
            specific_info = await sync_to_async(symptom_service.provide_specific_info)(
                message
            )
            
            # Combine general guidance with specific information
            if 'messages' in specific_info:
                response_data['messages'].extend(specific_info['messages'])
            
            # Log the interaction for audit purposes
            await self._log_symptom_interaction(
                message,
                symptom_analysis,
                risk_assessment,
                response_data
            )
            
            return JsonResponse(response_data), self.session
            
        except Exception as e:
            logger.error(f"Error in symptom handler: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": [
                    "I apologize, but I encountered an error processing your symptoms.",
                    "If you're experiencing a medical emergency, please call emergency services immediately."
                ]
            }), self.session
            
    async def _log_symptom_interaction(self, original_message, analysis, assessment, response):
        """Log the symptom interaction for audit purposes"""
        try:
            interaction_log = {
                'timestamp': datetime.utcnow().isoformat(),
                'patient_id': self.patient_id,
                'original_message': original_message,
                'symptom_analysis': analysis,
                'risk_assessment': assessment,
                'response_given': response,
                'session_id': self.session.get('id')
            }
            
            await sync_to_async(logger.info)(f"Symptom interaction logged: {json.dumps(interaction_log)}")
            
        except Exception as e:
            await sync_to_async(logger.error)(f"Error logging symptom interaction: {str(e)}")

    async def handle_procedures_query(self):
        """Handle request to show patient's procedures"""
        try:
            if not self.patient_id:
                return JsonResponse({"messages": ["I couldn't find your patient records."]}), self.session

            # Get procedures from FHIR server
            procedures = await self.fhir_client.search('Procedure',
                params={'patient': self.patient_id, '_sort': '-date'})

            if procedures and procedures.get('entry'):
                formatted_procedures = ['Your past procedures are:']
                for entry in procedures['entry']:
                    procedure = entry['resource']
                    name = procedure.get('code', {}).get('text', 'Unknown procedure')
                    date = procedure.get('performedDateTime', '').split('T')[0]
                    formatted_procedures.append(f"- {name} (Date: {date})")
                return JsonResponse({"messages": formatted_procedures}), self.session
            return JsonResponse({
                "messages": ["I couldn't find any procedures in your medical record."]
            }), self.session

        except Exception as e:
            logger.error(f"Error fetching procedures: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": ["I'm having trouble accessing your procedure records right now."]
            }), self.session

    async def _create_appointment(self, slot, booking_state, parsed_datetime):
        """Create the actual appointment with all necessary details"""
        try:
            logger.info(f"Creating appointment for slot: {slot}")

            # Get the slot resource correctly
            slot_resource = slot.get('resource', slot)

            # Create the appointment resource
            appointment = {
                'resourceType': 'Appointment',
                'status': 'booked',
                'appointmentType': {
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/v2-0276',
                        'code': booking_state['appointment_info']['type'],
                        'display': booking_state['appointment_info']['type']
                    }]
                },
                'description': booking_state['appointment_info']['reason'],
                'start': slot_resource['start'],
                'end': slot_resource['end'],
                'minutesDuration': 30,
                'slot': [
                    {'reference': f"Slot/{slot_resource['id']}"}
                ],
                'participant': [
                    {
                        'actor': {
                            'reference': f"Patient/{self.patient_id}",
                            'type': 'Patient'
                        },
                        'status': 'accepted'
                    },
                    {
                        'actor': {
                            'reference': f"Practitioner/{booking_state['selected_practitioner']}",
                            'type': 'Practitioner'
                        },
                        'status': 'accepted'
                    }
                ],
                'created': datetime.now(ZoneInfo("UTC")).isoformat()
            }

            # Create the appointment
            logger.info("Attempting to create appointment in FHIR")
            created_appointment = await self.fhir_client.create('Appointment', appointment)

            if not created_appointment:
                raise Exception("Failed to create appointment in FHIR")

            # Update the slot status to booked
            logger.info("Updating slot status to booked")
            slot_resource['status'] = 'busy'
            await self.fhir_client.update('Slot', slot_resource['id'], slot_resource)

            # Clear booking state
            self.session.pop('booking_state', None)
            await update_session(self.user_id, self.session)

            # Format the confirmation message
            clinic_tz = self._get_clinic_timezone()
            formatted_time = await self._format_appointment_time(parsed_datetime.isoformat())

            return JsonResponse({
                "messages": [
                    f"Great! I've booked your {booking_state['appointment_info']['type']} appointment:\n\n"
                    f"Provider: Dr. {booking_state['appointment_info']['practitioner_name']}\n"
                    f"Date/Time: {formatted_time}\n"
                    f"Reason: {booking_state['appointment_info']['reason']}\n\n"
                    "You'll receive a confirmation email shortly. Is there anything else I can help you with?"
                ]
            }), self.session

        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}", exc_info=True)
            self.session.pop('booking_state', None)
            await update_session(self.user_id, self.session)
            return JsonResponse({
                "messages": ["I'm sorry, there was an error creating your appointment. Please try again."]
            }), self.session

    async def send_message(self, to_number, message):
        """Send SMS message using Twilio"""
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_number
            )
            logger.info(f"SMS sent successfully to {to_number}: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Error sending SMS to {to_number}: {str(e)}")
            return False

    async def _handle_show_appointments(self, message=None, intent_data=None, user_id=None):
        """Handle showing appointments for a user.

        Args:
            message: The user's message
            intent_data: Intent data from NLP
            user_id: The user's ID (optional, falls back to self.user_id)
        """
        try:
            if not self.patient or not self.patient.get('email'):
                return JsonResponse({
                    "messages": ["Please verify your email first to view your appointments."]
                }), self.session

            patient_email = self.patient['email']
            patient_id = self.patient['id']
            logger.info(f"Fetching appointments for patient email: {patient_email}")

            # Get current time in UTC
            current_time = datetime.now(ZoneInfo("UTC")).isoformat()

            # Search for appointments using patient ID directly
            appointment_params = {
                "patient": f"Patient/{patient_id}",
                "date": f"ge{current_time}",
                "_sort": "date"
            }

            logger.debug(f"Searching appointments with params: {appointment_params}")
            appointments = await self.fhir_service.search("Appointment", appointment_params)

            if not appointments or 'entry' not in appointments or not appointments['entry']:
                return JsonResponse({
                    "messages": ["You don't have any upcoming appointments scheduled."]
                }), self.session

            # Format appointments
            messages = ["Here are your upcoming appointments:"]

            for entry in appointments['entry']:
                appointment = entry['resource']

                # Skip non-booked appointments
                if appointment.get('status') not in ['booked', 'pending']:
                    continue

                # Format the appointment time
                start_time = datetime.fromisoformat(appointment['start'].replace('Z', '+00:00'))
                formatted_time = await self._format_appointment_time(appointment['start'])

                # Get practitioner info from participants
                practitioner_name = "Unknown Provider"
                for participant in appointment.get('participant', []):
                    actor = participant.get('actor', {})
                    if actor.get('type') == 'Practitioner' or 'Practitioner/' in actor.get('reference', ''):
                        practitioner_ref = actor['reference'].split('/')[-1]
                        practitioner = await sync_to_async(self.fhir_service.read)('Practitioner', practitioner_ref)
                        if practitioner:
                            practitioner_name = get_resource_name(practitioner)
                        break

                # Build appointment info string
                appt_info = f"- {formatted_time} with {practitioner_name}"

                # Add reason if available
                if appointment.get('description'):
                    appt_info += f" ({appointment['description']})"
                elif appointment.get('reason'):
                    appt_info += f" ({appointment['reason'][0].get('text', 'No reason provided')})"

                messages.append(appt_info)

            if len(messages) == 1:  # Only header message
                return JsonResponse({
                    "messages": ["You don't have any upcoming appointments scheduled."]
                }), self.session

            return JsonResponse({
                "messages": messages
            }), self.session

        except Exception as e:
            logger.error(f"Error showing appointments: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": ["I'm sorry, I couldn't retrieve your appointments at this time. Please try again later."]
            }), self.session

    async def _handle_height_query(self):
        """Handle request to show patient's height"""
        try:
            logger.debug("Handling height query")
            if not self.patient or not self.patient.get('resource'):
                return JsonResponse({"messages": ["I couldn't find your patient records."]}), self.session

            # Get height from patient resource extensions
            patient_resource = self.patient['resource']
            height_extension = next(
                (ext for ext in patient_resource.get('extension', [])
                 if ext['url'] == "http://example.org/fhir/StructureDefinition/height"),
                None
            )

            if height_extension and 'valueQuantity' in height_extension:
                height_value = height_extension['valueQuantity']['value']
                height_unit = height_extension['valueQuantity']['unit']
                logger.debug(f"Found height: {height_value} {height_unit}")
                return JsonResponse({"messages": [f"Your height is {height_value} {height_unit}."]}), self.session

            return JsonResponse({"messages": ["I couldn't find your height information in your records."]}), self.session

        except Exception as e:
            logger.error(f"Error fetching height: {str(e)}", exc_info=True)
            return JsonResponse({"messages": ["I'm sorry, I couldn't retrieve your height information at this time."]}), self.session

    async def _handle_greeting(self, message=None, intent_data=None):
        try:
            if self.patient and self.patient.get('resource'):
                name = self.patient['resource'].get('name', [{}])[0]
                if name and name.get('given') and name.get('family'):
                    greeting = f"Hello {name.get('given', [''])[0]} {name.get('family')}! How can I help you today?"
                    return JsonResponse({"messages": [greeting]}), self.session

            return JsonResponse({"messages": ["Hello! How can I help you today?"]}), self.session
        except Exception as e:
            logger.error(f"Error in greeting: {str(e)}")
            return JsonResponse({"messages": ["Hello! How can I help you today?"]}), self.session

    async def handle_medications_query(self):
        """Handle request to show patient's medications"""
        try:
            if not self.patient_id:
                return JsonResponse({"messages": ["I couldn't find your patient records."]}), self.session

            # Wrap synchronous search methods with sync_to_async
            medication_statements = await sync_to_async(self.fhir_client.search)('MedicationStatement',
                params={'patient': f"Patient/{self.patient_id}", 'status': 'active'})

            medication_requests = await sync_to_async(self.fhir_client.search)('MedicationRequest',
                params={'patient': f"Patient/{self.patient_id}", 'status': 'active'})

            medications = []

            # Process MedicationStatements
            if medication_statements and medication_statements.get('entry'):
                for entry in medication_statements['entry']:
                    med = entry['resource']
                    name = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display', 'Unknown medication')
                    dosage = med.get('dosage', [{}])[0].get('text', 'No dosage information')
                    medications.append(f"- {name} ({dosage})")

            # Process MedicationRequests
            if medication_requests and medication_requests.get('entry'):
                for entry in medication_requests['entry']:
                    med = entry['resource']
                    name = med.get('medicationCodeableConcept', {}).get('text', 'Unknown medication')
                    dosage = med.get('dosageInstruction', [{}])[0].get('text', 'No dosage information')
                    medications.append(f"- {name} ({dosage})")

            if medications:
                formatted_meds = ['Your current medications are:']
                formatted_meds.extend(medications)
                await update_session(self.user_id, self.session)
                return JsonResponse({"messages": formatted_meds}), self.session

            await update_session(self.user_id, self.session)
            return JsonResponse({
                "messages": ["I couldn't find any active medications in your records."]
            }), self.session

        except Exception as e:
            logger.error(f"Error fetching medications: {str(e)}", exc_info=True)
            await update_session(self.user_id, self.session)
            return JsonResponse({
                "messages": ["I'm having trouble accessing your medication records right now."]
            }), self.session

    async def _handle_medical_record(self):
        logger.debug("=== Medical Record Query Debug ===")
        logger.debug(f"Patient data: {self.patient}")
        logger.debug(f"Patient ID: {self.patient_id}")

        """Handle request to show complete medical record"""
        try:
            if not self.patient_id:
                return JsonResponse({
                    "messages": ["I couldn't access your medical records. Please ensure you're logged in."]
                }), self.session

            # Initialize the record list
            record = []
            patient_resource = self.patient['resource']

            # Basic Information
            record.append("PERSONAL INFORMATION:")
            name = patient_resource.get('name', [{}])[0]
            full_name = f"{name.get('given', [''])[0]} {name.get('family', '')}"
            record.append(f"Name: {full_name}")
            record.append(f"Gender: {patient_resource.get('gender', 'Not specified')}")
            record.append(f"Birth Date: {patient_resource.get('birthDate', 'Not specified')}")

            # Vital Signs
            record.append("\nVITAL SIGNS:")
            for extension in patient_resource.get('extension', []):
                if extension['url'].endswith('height'):
                    value = extension.get('valueQuantity', {})
                    record.append(f"Height: {value.get('value')} {value.get('unit')}")
                elif extension['url'].endswith('weight'):
                    value = extension.get('valueQuantity', {})
                    record.append(f"Weight: {value.get('value')} {value.get('unit')}")

            # Contact Information
            record.append("\nCONTACT INFORMATION:")
            for telecom in patient_resource.get('telecom', []):
                system = telecom.get('system', '').title()
                value = telecom.get('value', '')
                record.append(f"{system}: {value}")

            # Emergency Contacts
            record.append("\nEMERGENCY CONTACTS:")
            contacts = await sync_to_async(self.fhir_client.search)("RelatedPerson", {
                "patient": f"Patient/{self.patient_id}"
            })
            if contacts and contacts.get('entry'):
                for entry in contacts['entry']:
                    contact = entry['resource']
                    relationship = contact.get('relationship', [{}])[0].get('text', 'Contact')
                    name = contact.get('name', [{}])[0]
                    contact_name = f"{name.get('given', [''])[0]} {name.get('family', '')}"
                    record.append(f"- {relationship}: {contact_name}")
                    for telecom in contact.get('telecom', []):
                        record.append(f"  {telecom.get('system', '').title()}: {telecom.get('value', '')}")
            else:
                record.append("No emergency contacts listed")

            # Allergies
            record.append("\nALLERGIES:")
            allergies = await sync_to_async(self.fhir_client.search)("AllergyIntolerance", {
                "patient": f"Patient/{self.patient_id}"
            })
            if allergies and allergies.get('entry'):
                for entry in allergies['entry']:
                    allergy = entry['resource']
                    substance = (allergy.get('code', {}).get('text') or
                               allergy.get('code', {}).get('coding', [{}])[0].get('display', 'Unknown'))
                    severity = allergy.get('reaction', [{}])[0].get('severity', 'unknown')
                    record.append(f"- {substance} (Severity: {severity})")
            else:
                record.append("No known allergies")

            # Social History
            record.append("\nSOCIAL HISTORY:")
            social_history = await sync_to_async(self.fhir_client.search)("Observation", {
                "patient": f"Patient/{self.patient_id}",
                "category": "social-history"
            })
            if social_history and social_history.get('entry'):
                for entry in social_history['entry']:
                    observation = entry['resource']
                    record.append(f"- {observation.get('code', {}).get('text')}: {observation.get('valueString', '')}")
            else:
                record.append("No social history recorded")

            # Healthcare Providers
            record.append("\nHEALTHCARE PROVIDERS:")
            providers = await sync_to_async(self.fhir_client.search)("PractitionerRole", {
                "patient": f"Patient/{self.patient_id}"
            })
            if providers and providers.get('entry'):
                for entry in providers['entry']:
                    provider = entry['resource']
                    role = provider.get('specialty', [{}])[0].get('text', 'Healthcare Provider')
                    practitioner = provider.get('practitioner', {}).get('display', 'Unknown')
                    record.append(f"- {role}: Dr. {practitioner}")
            else:
                record.append("No healthcare providers listed")

            # ----------- Fetching Medical Conditions -----------
            try:
                # First attempt: Fetch active, relapse, and recurrence conditions sorted by recorded-date
                conditions = await sync_to_async(self.fhir_client.search)("Condition", {
                    "patient": f"Patient/{self.patient_id}",
                    "_sort": "-recorded-date",  # Corrected sort parameter
                    "clinical-status": "active,relapse,recurrence"  # Ensure these are valid statuses
                })

                logger.debug(f"Conditions response: {json.dumps(conditions)}")  # Debug logging

                # If no conditions found, try fetching all conditions sorted by recorded-date
                if not conditions or not conditions.get('entry'):
                    conditions = await sync_to_async(self.fhir_client.search)("Condition", {
                        "patient": f"Patient/{self.patient_id}",
                        "_sort": "-recorded-date"  # Corrected sort parameter
                    })
                    logger.debug(f"Conditions response after second attempt: {json.dumps(conditions)}")  # Debug logging

                if conditions and conditions.get('entry'):
                    record.append("\nMEDICAL CONDITIONS:")
                    for entry in conditions['entry']:
                        condition = entry['resource']

                        # Extract condition name
                        name = (condition.get('code', {}).get('text') or
                                condition.get('code', {}).get('coding', [{}])[0].get('display') or
                                'Unknown condition')

                        # Extract clinical status
                        clinical_status_obj = condition.get('clinicalStatus', {})
                        clinical_status = (clinical_status_obj.get('text') or
                                           clinical_status_obj.get('coding', [{}])[0].get('display') or
                                           clinical_status_obj.get('coding', [{}])[0].get('code', 'unknown'))

                        # Extract verification status
                        verification_obj = condition.get('verificationStatus', {})
                        verification_status = (verification_obj.get('text') or
                                               verification_obj.get('coding', [{}])[0].get('display') or
                                               verification_obj.get('coding', [{}])[0].get('code', ''))

                        # Extract onset date
                        onset_date = None
                        if condition.get('onsetDateTime'):
                            onset_date = condition['onsetDateTime'].split('T')[0]
                        elif condition.get('onsetPeriod', {}).get('start'):
                            onset_date = condition['onsetPeriod']['start'].split('T')[0]
                        elif condition.get('onsetString'):
                            onset_date = condition['onsetString']

                        # Build condition line
                        condition_line = f"- {name}"
                        if clinical_status and clinical_status.lower() != 'active':
                            condition_line += f" (Status: {clinical_status})"
                        if onset_date:
                            condition_line += f" (Onset: {onset_date})"
                        if verification_status and verification_status.lower() != 'confirmed':
                            condition_line += f" ({verification_status})"

                        record.append(condition_line)

                        # Add condition notes if available
                        if condition.get('note'):
                            for note in condition['note']:
                                if note.get('text'):
                                    record.append(f"  Note: {note['text']}")
                else:
                    record.append("\nMEDICAL CONDITIONS:")
                    record.append("No current medical conditions found")
            except Exception as e:
                logger.error(f"Error fetching conditions: {str(e)}", exc_info=True)
                record.append("\nMEDICAL CONDITIONS:")
                record.append("Error retrieving conditions")

            # ----------- Fetching Medications -----------
            try:
                medications = await sync_to_async(self.fhir_client.search)("MedicationRequest", {
                    "patient": f"Patient/{self.patient_id}",
                    "status": "active"
                })

                if medications and medications.get('entry'):
                    record.append("\nCURRENT MEDICATIONS:")
                    for entry in medications['entry']:
                        med = entry['resource']
                        name = (med.get('medicationCodeableConcept', {}).get('text') or
                                med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display') or
                                'Unknown medication')

                        dosage = med.get('dosageInstruction', [{}])[0]
                        dosage_text = (dosage.get('text') or
                                       f"{dosage.get('timing', {}).get('repeat', {}).get('frequency', 'as needed')} times per day")

                        record.append(f"- {name} ({dosage_text})")

                        # Add medication notes if available
                        if med.get('note'):
                            for note in med['note']:
                                if note.get('text'):
                                    record.append(f"  Note: {note['text']}")
                else:
                    record.append("\nCURRENT MEDICATIONS:")
                    record.append("No active medications found")

            except Exception as e:
                logger.error(f"Error fetching medications: {str(e)}")
                record.append("\nCURRENT MEDICATIONS:")
                record.append("Error retrieving medications")

            # ----------- Fetching Procedures -----------
            try:
                procedures = await sync_to_async(self.fhir_client.search)("Procedure", {
                    "patient": f"Patient/{self.patient_id}",
                    "_sort": "-recorded-date"  # Corrected sort parameter
                })

                if procedures and procedures.get('entry'):
                    record.append("\nPAST PROCEDURES:")
                    for entry in procedures['entry']:
                        procedure = entry['resource']
                        name = (procedure.get('code', {}).get('text') or
                                procedure.get('code', {}).get('coding', [{}])[0].get('display') or
                                'Unknown procedure')

                        date = procedure.get('performedDateTime', '').split('T')[0]
                        status = procedure.get('status', 'unknown')

                        procedure_line = f"- {name}"
                        if date:
                            procedure_line += f" (Date: {date})"
                        if status != 'completed':
                            procedure_line += f" (Status: {status})"

                        record.append(procedure_line)

                        # Add procedure notes if available
                        if procedure.get('note'):
                            for note in procedure['note']:
                                if note.get('text'):
                                    record.append(f"  Note: {note['text']}")
                else:
                    record.append("\nPAST PROCEDURES:")
                    record.append("No procedures found")

            except Exception as e:
                logger.error(f"Error fetching procedures: {str(e)}")
                record.append("\nPAST PROCEDURES:")
                record.append("Error retrieving procedures")

            # ----------- Fetching Immunizations -----------
            try:
                immunizations = await sync_to_async(self.fhir_client.search)("Immunization", {
                    "patient": f"Patient/{self.patient_id}"
                })

                if immunizations and immunizations.get('entry'):
                    record.append("\nIMMUNIZATIONS:")
                    for entry in immunizations['entry']:
                        immunization = entry['resource']
                        vaccine = (immunization.get('vaccineCode', {}).get('text') or
                                   immunization.get('vaccineCode', {}).get('coding', [{}])[0].get('display') or
                                   'Unknown vaccine')

                        date = immunization.get('occurrenceDateTime', '').split('T')[0]
                        status = immunization.get('status', 'unknown')

                        record.append(f"- {vaccine} (Date: {date}, Status: {status})")

                        # Add immunization notes if available
                        if immunization.get('note'):
                            for note in immunization['note']:
                                if note.get('text'):
                                    record.append(f"  Note: {note['text']}")
                else:
                    record.append("\nIMMUNIZATIONS:")
                    record.append("No immunization records found")

            except Exception as e:
                logger.error(f"Error fetching immunizations: {str(e)}")
                record.append("\nIMMUNIZATIONS:")
                record.append("Error retrieving immunizations")

            # Compile and return the complete medical record
            await update_session(self.user_id, self.session)
            return JsonResponse({
                "messages": ["Here is your complete medical record:\n\n" + "\n".join(record)]
            }), self.session

        except Exception as e:
            logger.error(f"Error handling medical record query: {str(e)}", exc_info=True)
            await update_session(self.user_id, self.session)
            return JsonResponse({
                "messages": ["I'm having trouble accessing your medical records right now."]
            }), self.session

    async def _handle_initial_choice(self):
        """Handle initial choice for finding healthcare provider"""
        try:
            if self.user_message.lower() == 'cancel':
                self.session.pop('booking_state', None)
                await update_session(self.user_id, self.session)
                return JsonResponse({
                    "messages": ["Booking cancelled. Is there anything else I can help you with?"]
                }), self.session

            if not self.user_message.isdigit() or self.user_message not in ['1', '2']:
                return JsonResponse({
                    "messages": [
                        "Please select a valid option:\n\n"
                        "1. Search by practitioner name\n"
                        "2. Search by role (Doctor, Nurse, Specialist)\n\n"
                        "Or type 'cancel' to stop booking."
                    ]
                }), self.session

            if self.user_message == '1':
                # Search by name
                practitioners = await self.fhir_service.get_available_practitioners()
                if not practitioners:
                    return JsonResponse({
                        "messages": ["I apologize, but no healthcare providers are currently available."]
                    }), self.session

                messages = ["Please select a practitioner by number:"]
                practitioner_map = {}
                for i, pract in enumerate(practitioners, 1):
                    name = pract['name']
                    specialty = pract.get('specialty', 'General Practice')
                    messages.append(f"{i}. {name} - {specialty}")
                    practitioner_map[str(i)] = pract['id']

                messages.append("\nEnter the number of your choice, or type 'cancel' to stop booking.")

                # Update booking state
                self.session['booking_state']['practitioners'] = practitioner_map
                self.session['booking_state']['step'] = 'select_practitioner'
                await update_session(self.user_id, self.session)

                return JsonResponse({"messages": messages}), self.session

            else:  # self.user_message == '2'
                # Get available practitioners
                practitioners = await self.fhir_service.get_available_practitioners()
                if not practitioners:
                    return JsonResponse({
                        "messages": ["I apologize, but no healthcare providers are currently available."]
                    }), self.session

                # Get unique roles
                roles = sorted(set(p.get('role', 'General Practitioner') for p in practitioners))
                messages = ["Please select a healthcare provider role:"]
                role_map = {}
                for i, role in enumerate(roles, 1):
                    messages.append(f"{i}. {role}")
                    role_map[str(i)] = role

                messages.append("\nEnter the number of your choice, or type 'cancel' to stop booking.")

                # Update booking state
                self.session['booking_state']['roles'] = role_map
                self.session['booking_state']['step'] = 'select_role'
                await update_session(self.user_id, self.session)

                return JsonResponse({"messages": messages}), self.session

        except Exception as e:
            logger.error(f"Error handling initial choice: {str(e)}", exc_info=True)
            return self._handle_booking_error()

    async def _handle_name_search(self, booking_state):
        """Handle practitioner name search"""
        try:
            if self.user_message.lower() == 'cancel':
                self.session.pop('booking_state', None)
                await update_session(self.user_id, self.session)
                return JsonResponse({
                    "messages": ["Booking cancelled. Is there anything else I can help you with?"]
                }), self.session

            # Search for practitioner by name
            practitioners = await self.fhir_service.get_available_practitioners(name=self.user_message)

            if not practitioners:
                return JsonResponse({
                    "messages": [
                        "No practitioners found with that name. Please try again with a different name.\n"
                        "Or type 'cancel' to stop booking."
                    ]
                }), self.session

            # Store practitioners and move to reason entry
            booking_state['practitioners'] = {str(i): p['id'] for i, p in enumerate(practitioners, 1)}
            booking_state['step'] = 'enter_reason'
            booking_state['selected_practitioner'] = practitioners[0]['id']  # Since we're searching by name
            self.session['booking_state'] = booking_state
            await update_session(self.user_id, self.session)

            practitioner_name = await get_resource_name(practitioners[0])
            return JsonResponse({
                "messages": [
                    f"Found Dr. {practitioner_name}.\n\n"
                    "Please provide a brief reason for your visit.\n"
                    "Or type 'cancel' to stop booking."
                ]
            }), self.session

        except Exception as e:
            logger.error(f"Error in name search: {str(e)}", exc_info=True)
            return self._handle_booking_error()


    async def _handle_immunizations_query(self):
        """Handle immunization/vaccine queries"""
        try:
            if not self.patient_id:
                return JsonResponse({
                    "messages": ["I couldn't find your patient records."]
                }), self.session

            medical_record = await get_complete_medical_record(self.patient_id)

            # Extract immunizations section from medical record
            if isinstance(medical_record, str):
                immunizations_section = ""
                capture_immunizations = False
                immunizations = []

                for line in medical_record.split('\n'):
                    if 'Immunizations:' in line:
                        capture_immunizations = True
                        continue
                    elif capture_immunizations and line.strip() and not line.startswith('7.'):
                        immunizations.append(line.strip())
                    elif capture_immunizations and line.startswith('7.'):
                        break

                if immunizations:
                    response = ["Your immunization record includes:"]
                    response.extend([f"- {imm}" for imm in immunizations if imm.strip()])
                    return JsonResponse({"messages": response})
            return JsonResponse({
                "messages": ["I couldn't find any immunization records in your file."]
            }), self.session

        except Exception as e:
            logger.error(f"Error handling immunizations query: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": ["I'm having trouble accessing your immunization records right now."]
            }), self.session

    async def detect_language(self, text):
        try:
            response = await self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a language detector. Respond only with the ISO language code."},
                    {"role": "user", "content": f"What language is this: {text}"}
                ]
            )
            detected = response.choices[0].message.content.strip().lower()
            # Ensure we return a string, not any other type
            return str(detected) if detected else 'en'
        except Exception as e:
            logger.error(f"Error detecting language: {str(e)}")
            return 'en'  # Default to English on error


    async def handle_conditions_query(self):
        """Handle request to view patient conditions"""
        try:
            if not self.patient_id:
                return JsonResponse({
                    "messages": ["I couldn't find your patient records."]
                }), self.session

            # Use sync_to_async to wrap the synchronous search method
            search_params = {
                "patient": f"Patient/{self.patient_id}",
                "_sort": "-recorded-date"
            }

            conditions_bundle = await sync_to_async(self.fhir_client.search)("Condition", search_params)

            if not conditions_bundle or 'entry' not in conditions_bundle:
                return JsonResponse({
                    "messages": ["I don't see any recorded conditions in your medical record."]
                }), self.session

            # Format conditions into readable text
            conditions_list = ["Your current conditions are:"]
            for entry in conditions_bundle['entry']:
                condition = entry['resource']
                name = condition.get('code', {}).get('coding', [{}])[0].get('display', 'Unknown condition')
                status = condition.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', 'unknown')

                condition_text = f"- {name} (Status: {status})"
                conditions_list.append(condition_text)
            return JsonResponse({
                "messages": conditions_list
            }), self.session

        except Exception as e:
            logger.error(f"Error retrieving conditions: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": ["I'm having trouble accessing your conditions right now. Please try again later."]
            }), self.session



    async def _handle_type_selection(self, booking_state):
        """Handle selection of practitioner role"""
        try:
            if self.user_message.lower() == 'cancel':
                self.session.pop('booking_state', None)
                await update_session(self.user_id, self.session)
                return JsonResponse({
                    "messages": ["Booking cancelled. Is there anything else I can help you with?"]
                }), self.session

            roles = booking_state.get('roles', {})
            if not roles:
                logger.error("No roles dictionary in booking state")
                return self._handle_booking_error()

            if not self.user_message.isdigit() or self.user_message not in roles:
                messages = ["Please select a valid role number:"]
                for i, role in roles.items():
                    messages.append(f"{i}. {role}")
                messages.append("\nOr type 'cancel' to stop booking.")
                return JsonResponse({"messages": messages}), self.session

            selected_role = roles[self.user_message]

            # Get practitioners with the selected role
            all_practitioners = await self.fhir_service.get_available_practitioners()
            role_practitioners = [p for p in all_practitioners if p.get('role') == selected_role]

            if not role_practitioners:
                return JsonResponse({
                    "messages": [f"I apologize, but no {selected_role}s are currently available."]
                }), self.session

            # Create numbered list of practitioners
            messages = [f"Please select a {selected_role} by number:"]
            practitioner_map = {}
            for i, pract in enumerate(role_practitioners, 1):
                name = pract['name']
                specialty = pract.get('specialty', 'General Practice')
                messages.append(f"{i}. {name} - {specialty}")
                practitioner_map[str(i)] = pract['id']

            messages.append("\nEnter the number of your choice, or type 'cancel' to stop booking.")

            # Update booking state
            booking_state['practitioners'] = practitioner_map
            booking_state['step'] = 'select_practitioner'
            self.session['booking_state'] = booking_state
            await update_session(self.user_id, self.session)

            return JsonResponse({"messages": messages}), self.session

        except Exception as e:
            logger.error(f"Error handling role selection: {str(e)}", exc_info=True)
            return self._handle_booking_error()

    async def _handle_reason_entry(self, booking_state):
        """Handle the entry of appointment reason"""
        try:
            if self.user_message.lower() == 'cancel':
                self.session.pop('booking_state', None)
                await update_session(self.user_id, self.session)
                return JsonResponse({
                    "messages": ["Booking cancelled. Is there anything else I can help you with?"]
                }), self.session

            # Store the reason and update step
            booking_state['appointment_info']['reason'] = self.user_message
            booking_state['step'] = 'select_datetime'
            self.session['booking_state'] = booking_state
            await update_session(self.user_id, self.session)

            return JsonResponse({
                "messages": [
                    "Please enter your preferred date and time for the appointment.\n\n"
                    "For example:\n"
                    "- Tomorrow at 2pm\n"
                    "- Next Tuesday at 10:30am\n"
                    "- December 1st at 3pm\n\n"
                    "Our hours are 9 AM to 5 PM, Monday through Friday."
                ]
            }), self.session

        except Exception as e:
            logger.error(f"Error in reason entry: {str(e)}")
            return self._handle_booking_error()

    async def _parse_datetime_with_timezone(self, datetime_string):
        """
        Parse a natural language datetime string with multiple fallback strategies:
        1. Attempt direct parsing with 'dateparser'.
        2. Validate business hours and days.
        3. If fails, return a helpful error message.

        Returns:
            (datetime or None, error_message or None)
        """
        try:
            # 1. Use dateparser for natural language date-time handling.
            #    Set a base reference time if needed, e.g., now in UTC.
            now = datetime.now(ZoneInfo("UTC"))
            parsed = dateparser.parse(
                datetime_string,
                settings={
                    'RETURN_AS_TIMEZONE_AWARE': True,
                    'TIMEZONE': 'UTC',
                    'RELATIVE_BASE': now,
                    'PREFER_DATES_FROM': 'future'
                }
            )

            if not parsed:
                # Could not parse at all
                return None, "I couldn't understand that date/time. Please try a more standard format like 'December 9th at 1pm' or 'next Monday at 2 PM'."

            # If the parsed date is today or in the past, assume user meant next occurrence
            if parsed.date() <= now.date():
                # Get the target weekday (0 = Monday, 6 = Sunday)
                target_weekday = parsed.weekday()
                current_weekday = now.weekday()

                # Calculate days until next occurrence
                days_ahead = target_weekday - current_weekday
                if days_ahead <= 0:  # Target day already passed this week
                    days_ahead += 7

                # Adjust the date to next occurrence
                parsed = parsed.replace(year=now.year, month=now.month, day=now.day) + timedelta(days=days_ahead)

            # 2. Validate business rules: Monday-Friday, 9-17 hours
            if parsed.weekday() >= 5:
                # Weekend
                return None, "We are only open Monday through Friday. Please choose a weekday."

            # Business hours check
            if not (9 <= parsed.hour < 17):
                return None, "Our hours are 9 AM to 5 PM. Please select a time within these hours."

            # Round to the nearest 30-minute increment
            minutes = parsed.minute
            rounded_minutes = 0 if minutes < 30 else 30
            parsed = parsed.replace(minute=rounded_minutes, second=0, microsecond=0)

            return parsed, None

        except Exception as e:
            logger.error(f"Error parsing datetime: {str(e)}", exc_info=True)
            return None, "There was an error processing your date/time selection. Please try again."
    async def _format_appointment_time(self, datetime_str):
        """
        Format datetime string into user-friendly format.
        Args:
            datetime_str: ISO format datetime string
        Returns:
            Formatted string like "Tuesday, November 21st at 2:00 PM"
        """
        try:
            # Parse the ISO datetime string
            if isinstance(datetime_str, str):
                if datetime_str.endswith('Z'):
                    datetime_str = datetime_str[:-1] + '+00:00'
                dt = datetime.fromisoformat(datetime_str)
            else:
                dt = datetime_str

            # Ensure timezone is UTC if none specified
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))

            # Convert to local timezone
            local_dt = dt.astimezone(ZoneInfo(settings.TIME_ZONE))

            # Format date components
            day_name = local_dt.strftime("%A")
            month = local_dt.strftime("%B")
            day = local_dt.day

            # Add ordinal suffix
            suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

            # Format time
            time_str = local_dt.strftime("%I:%M %p").lstrip("0")

            return f"{day_name}, {month} {day}{suffix} at {time_str}"

        except Exception as e:
            logger.error(f"Error formatting appointment time: {str(e)}", exc_info=True)
            return str(datetime_str)


    async def _handle_appointment_booking(self, message, intent_data=None, user_id=None):
        """Handle appointment booking requests"""
        try:
            logger.debug("Handling appointment booking request")

            # Get available practitioners
            practitioners = await get_available_practitioners(self.fhir_client)

            # Get available slots
            available_slots = await search_available_slots(self.fhir_client)

            if not practitioners or not available_slots:
                return JsonResponse({
                    "messages": ["I apologize, but there are no available appointment slots at this time."],
                    "type": "error"
                }), self.session

            return JsonResponse({
                "messages": ["Please select a healthcare provider and preferred time from the available slots:"],
                "type": "appointment_booking",
                "data": {
                    "practitioners": practitioners,
                    "available_slots": available_slots
                }
            }), self.session

        except Exception as e:
            logger.error(f"Error handling appointment booking: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": ["I apologize, but I couldn't process your appointment booking request at this time."],
                "type": "error"
            }), self.session

    async def _handle_reschedule_request(self):
        """Handle appointment rescheduling requests."""
        try:
            if not self.patient_id:
                return JsonResponse({
                    "messages": ["Please verify your identity first to reschedule appointments."]
                }), self.session

            # Fetch upcoming appointments
            appointments = await get_patient_appointments(self.patient_id)
            if not appointments:
                return JsonResponse({
                    "messages": ["You don't have any upcoming appointments to reschedule."]
                }), self.session

            # Format appointment list for selection
            messages = ["Which appointment would you like to reschedule?"]
            appointment_map = {}
            for i, appt in enumerate(appointments, 1):
                formatted_time = await self._format_appointment_time(appt["start"])
                messages.append(f"{i}. {formatted_time} with {appt['provider']}")
                appointment_map[str(i)] = appt["id"]

            messages.append("\nEnter the number of the appointment you'd like to reschedule.")

            # Store selection context
            self.session["reschedule_options"] = appointment_map
            await update_session(self.user_id, self.session)

            return JsonResponse({"messages": messages})
        except Exception as e:
            logger.error(f"Error handling reschedule request: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": ["I'm having trouble retrieving your appointments. Please try again later."]
            }), self.session

    async def _handle_lab_results(self, message=None, intent_data=None, user_id=None):
        """Handle requests to view lab results"""
        try:
            if not self.patient_id:
                return JsonResponse({
                    "messages": ["Please verify your identity first to view your lab results."]
                }), self.session

            logger.debug(f"Fetching lab results for patient {self.patient_id}")

            # Try a simpler query first
            try:
                # First, try just getting DiagnosticReport without includes
                diagnostic_reports = await self.fhir_service.search("DiagnosticReport", {
                    "patient": f"Patient/{self.patient_id}",
                    "_sort": "-date"
                })

                logger.debug(f"Initial query response: {diagnostic_reports}")

                if not diagnostic_reports or 'entry' not in diagnostic_reports:
                    # Try alternative category coding
                    diagnostic_reports = await self.fhir_service.search("DiagnosticReport", {
                        "patient": f"Patient/{self.patient_id}",
                        "category": "LAB",
                        "_sort": "-date"
                    })
                    if not diagnostic_reports or 'entry' not in diagnostic_reports:
                        return JsonResponse({
                            "messages": ["No lab results found in your records."]
                        }), self.session

            except Exception as query_error:
                logger.error(f"Error in initial lab results query: {str(query_error)}")
                # Try fallback query
                diagnostic_reports = await self.fhir_service.search("DiagnosticReport", {
                    "patient": self.patient_id,  # Try without Patient/ prefix
                    "_sort": "-date"
                })

            # Format the results
            formatted_results = ["Here are your lab results:"]

            if diagnostic_reports and 'entry' in diagnostic_reports:
                for entry in diagnostic_reports['entry']:
                    report = entry['resource']
                    if report['resourceType'] != 'DiagnosticReport':
                        continue

                    # Get basic report info
                    date = report.get('effectiveDateTime', report.get('issued', '')).split('T')[0]

                    # Try different ways to get the category
                    category = None
                    if 'category' in report:
                        for cat in report['category']:
                            if 'text' in cat:
                                category = cat['text']
                                break
                            elif 'coding' in cat:
                                for coding in cat['coding']:
                                    if coding.get('display'):
                                        category = coding['display']
                                        break

                    category = category or 'Laboratory'

                    formatted_results.append(f"\n📋 {category} Report ({date})")

                    # Add the conclusion if available
                    if report.get('conclusion'):
                        formatted_results.append(f"Conclusion: {report['conclusion']}")

                    # Get the actual results
                    if 'result' in report:
                        try:
                            for result_ref in report['result']:
                                # Try to get the referenced observation
                                obs_id = result_ref['reference'].split('/')[-1]
                                observation = await self.fhir_service.read("Observation", obs_id)

                                if observation:
                                    test_name = observation.get('code', {}).get('text', 'Unknown Test')
                                    value = observation.get('valueQuantity', {})
                                    if value:
                                        value_str = f"{value.get('value', '')} {value.get('unit', '')}"
                                        formatted_results.append(f"- {test_name}: {value_str}")
                                    else:
                                        # Handle non-numeric results
                                        value_str = observation.get('valueString',
                                                  observation.get('valueCodeableConcept', {}).get('text',
                                                  'No value recorded'))
                                        formatted_results.append(f"- {test_name}: {value_str}")
                        except Exception as obs_error:
                            logger.error(f"Error fetching observation details: {str(obs_error)}")
                            formatted_results.append("- Unable to fetch detailed results")

            if len(formatted_results) == 1:  # Only has the header
                return JsonResponse({
                    "messages": ["No lab results found in your records."]
                }), self.session

            logger.debug("Successfully formatted lab results")
            return JsonResponse({
                "messages": formatted_results
            }), self.session

        except Exception as e:
            logger.error(f"Error handling lab results: {str(e)}", exc_info=True)
            return JsonResponse({
                "messages": ["I'm having trouble retrieving your lab results right now. Please try again later."]
            }), self.session

    async def _analyze_lab_question(self, message, lab_results):
        """Analyze the user's question about lab results with improved context"""
        try:
            # Get the last lab topic from session if it exists
            last_lab_context = self.session.get('last_lab_context', {})

            response = await self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are a medical lab result analyzer.
                        If the question appears to be a follow-up, use the previous lab context.
                        Analyze the user's question and return a JSON structure with:
                        - test_name: The specific test being asked about (or use previous context if it's a follow-up)
                        - comparison_type: "value", "trend", or "reference_range"
                        - temporal_context: "most_recent", "specific_date", or "trend"
                        - question_type: "interpretation", "comparison", or "general"
                        - is_followup: true if this appears to be a follow-up question
                        """
                    },
                    {
                        "role": "user",
                        "content": f"""
                        Previous lab context: {json.dumps(last_lab_context)}
                        Current question: {message}
                        Available results: {lab_results}
                        """
                    }
                ]
            )

            analysis = json.loads(response.choices[0].message.content)

            # Update session with current lab context
            self.session['last_lab_context'] = {
                'test_name': analysis.get('test_name'),
                'last_query': message,
                'timestamp': datetime.now().isoformat()
            }

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing lab question: {str(e)}")
            raise

    async def _find_specific_result(self, lab_results_response, test_info):
        """Find specific lab result with improved logging"""
        try:
            test_name = test_info['test_name'].lower()
            target_date = test_info.get('target_date')
            logger.debug(f"Looking for test: {test_name}")

            # Extract messages from JsonResponse
            if hasattr(lab_results_response, 'content'):
                content = json.loads(lab_results_response.content.decode())
                messages = content.get('messages', [])
            else:
                messages = lab_results_response.get('messages', [])

            logger.debug(f"Processing messages: {messages}")

            current_date = None
            for message in messages:
                if 'Date:' in message:
                    current_date = message.replace('Date:', '').strip()
                    logger.debug(f"Found date: {current_date}")
                elif test_name in message.lower():
                    logger.debug(f"Found matching test: {message}")
                    # Extract test details using regex
                    match = re.match(r'-\s*([^:]+):\s*(\d+\.?\d*)\s*([^\s\(]+)(?:\s*\(Reference Range:\s*([^\)]+)\))?', message)
                    if match:
                        return {
                            'test_name': match.group(1).strip(),
                            'value': match.group(2),
                            'unit': match.group(3),
                            'reference_range': match.group(4) if match.group(4) else None,
                            'date': current_date
                        }

            return None

        except Exception as e:
            logger.error(f"Error finding specific result: {str(e)}")
            return None

    async def _format_lab_response(self, result, test_info):
        """Format lab result with educational context only - flexible for any biomarker"""
        try:
            test_name = result.get('test_name', '')
            value = result.get('value', '')
            unit = result.get('unit', '')
            ref_range = result.get('reference_range', '')
            date = result.get('date', '')

            # Basic result and range information
            response = [
                f"For your {test_name} from {date}:",
                f"Value: {value} {unit}",
                f"Reference Range: {ref_range}\n"
            ]

            try:
                current_value = float(value.split()[0])
                range_parts = ref_range.split('-')
                if len(range_parts) == 2:
                    low = float(range_parts[0])
                    high = float(range_parts[1])

                    # Simple position relative to range
                    if current_value < low:
                        response.append("This result is below the reference range.")
                    elif current_value > high:
                        response.append("This result is above the reference range.")
                    else:
                        response.append("This result is within the reference range.")

            except (ValueError, IndexError) as e:
                logger.error(f"Error analyzing values: {str(e)}")

            # Generic educational disclaimer for any biomarker
            response.extend([
                "\nImportant notes:",
                "- Laboratory results can be affected by many factors including:",
                "  • Diet and nutrition",
                "  • Physical activity",
                "  • Time of day",
                "  • Medications",
                "  • Sample collection and handling",
                "",
                "- This information is for educational purposes only",
                "- Always consult your healthcare provider for medical advice",
                "- Your healthcare provider will interpret these results in the context of your overall health"
            ])

            return "\n".join(response)

        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            return "Error displaying results. Please consult your healthcare provider."
    async def _handle_screening(self, message=None, intent_data=None):
       """Placeholder for screening intent handler."""
       return ["This is a placeholder for screening information."], self.session

    async def _parse_lab_query(self, query, context=None):
        """Parse lab query with improved date handling and context awareness"""
        try:
            test_info = {
                'test_name': None,
                'temporal_context': 'most_recent',
                'target_date': None
            }

            # Extract test name
            test_names = {
                'potassium': ['potassium', 'k+'],
                'glucose': ['glucose', 'blood sugar', 'sugar'],
                'hemoglobin': ['hemoglobin', 'hgb', 'hb'],
                # Add more test mappings
            }

            # Check for test name in query
            for test, aliases in test_names.items():
                if any(alias in query for alias in aliases):
                    test_info['test_name'] = test
                    break

            # If no test found but we have context, use that
            if not test_info['test_name'] and context and context.get('last_test'):
                test_info['test_name'] = context['last_test']

            # Parse dates using improved regex patterns
            date_patterns = [
                # Natural language dates
                r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
                r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|'
                r'dec(?:ember)?)\s+\d+(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?',
                # ISO format dates
                r'\d{4}-\d{2}-\d{2}',
                # Other common formats
                r'\d{2}/\d{2}/\d{4}'
            ]

            for pattern in date_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    test_info['temporal_context'] = 'specific_date'
                    test_info['target_date'] = await self._normalize_date(match.group())
                    break

            return test_info

        except Exception as e:
            logger.error(f"Error parsing lab query: {str(e)}")
            return {'test_name': None, 'temporal_context': 'most_recent', 'target_date': None}

    async def _normalize_date(self, date_str):
        """Convert various date formats to ISO format"""
        try:
            # Try parsing natural language dates
            if any(month in date_str.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                                          'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                # Remove ordinal indicators and clean up
                date_str = re.sub(r'(st|nd|rd|th)', '', date_str)
                # Add current year if not specified
                if not re.search(r'\d{4}', date_str):
                    date_str = f"{date_str}, {datetime.now().year}"
                return datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")

            # Handle other common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue

            raise ValueError(f"Unable to parse date: {date_str}")

        except Exception as e:
            logger.error(f"Error normalizing date {date_str}: {str(e)}")
            return None
    def _get_clinic_timezone(self):
        """Get the clinic timezone from settings or use default"""
        try:
            return ZoneInfo(settings.TIME_ZONE) if hasattr(settings, 'TIME_ZONE') else ZoneInfo("UTC")
        except Exception as e:
            logger.error(f"Error getting clinic timezone: {str(e)}")
            return ZoneInfo("UTC")  # Default to UTC


    async def _update_session(self):
        """Update session state"""
        try:
            self.session['last_interaction'] = datetime.now().isoformat()
            self.session['verified'] = True
            await update_session(self.user_id, self.session)
        except Exception as e:
            logger.error(f"Error updating session: {str(e)}")
            raise

    async def _handle_capabilities_query(self):
        capabilities = [
            "Schedule new medical appointments",
            "View your upcoming appointments",
            "Cancel existing appointments",
            "Access and explain your medical records, including:",
            "   • Current conditions",
            "   • Active medications",
            "   • Recent procedures",
            "View and explain your test results",
            "Receive medication reminders",
            "Get notifications for annual screenings and check-ups",
            "Answer questions about your health information",
            "Provide general medical information and guidance",
            "Send appointment reminders via SMS",
            "Communicate through email notifications"
        ]

        response_text = "I can help you with:\n\n" + "\n".join(capabilities) + \
                   "\n\nPlease note: While I can provide information and explanations based on your medical records, " + \
                   "I am not a substitute for professional medical advice. Always consult your healthcare provider " + \
                   "for medical decisions."

        return JsonResponse({
            "messages": [response_text],
            "type": "capabilities"
        }), self.session

    async def _handle_explanation_query(self, message=None, intent_data=None):
        # Get the original text and check for context reset
        original_text = intent_data.get('entities', {}).get('original_text', '').lower()

        # Clear context if user explicitly states they're not talking about previous topic
        if 'not talking about' in original_text or 'i dont mean' in original_text:
            self.session.pop('last_topic', None)
            self.session.pop('last_context', None)
            await update_session(self.user_id, self.session)  # Ensure session update is persisted
            return JsonResponse({
                "messages": [
                    "I understand you want an explanation about something else. "
                    "Could you please specify what exactly you'd like me to explain? "
                    "I can help explain:"
                    "\n- Medical terms"
                    "\n- Test results"
                    "\n- Procedures"
                    "\n- Medications"
                    "\n- Or other health-related topics"
                ]
            }), self.session

        # Extract key terms from the topic to determine what needs explanation
        key_terms = {
            'check-up': 'regular medical check-ups and preventive care',
            'screening': 'medical screening and preventive tests',
            'vaccination': 'vaccinations and immunizations',
            'blood test': 'blood tests and laboratory work',
            'medication': 'medication adherence and treatment plans',
            'appointment': 'medical appointments and follow-ups',
            'test results': 'medical test results and monitoring',
            'symptoms': 'symptom monitoring and reporting'
        }

        topic = intent_data.get('entities', {}).get('topic', '')

        # Determine the explanation topic
        explanation_topic = None
        for term, description in key_terms.items():
            if term.lower() in topic.lower():
                explanation_topic = description
                break

        # If no specific term found, use a generic medical topic
        if not explanation_topic:
            explanation_topic = "general medical advice and recommendations"

        messages = [
            {
                "role": "system",
                "content": f"""You are a medical assistant providing clear explanations about {explanation_topic}.
                Explain the importance and benefits in simple terms, focusing on preventive care and health maintenance.
                Include:
                1. Why it's important
                2. Key benefits
                3. Potential risks of neglecting it
                4. General recommendations

                Keep the tone informative but reassuring."""
            },
            {
                "role": "user",
                "content": f"Please explain why {explanation_topic} is important for maintaining good health."
            }
        ]

        response = await self.openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7
        )

        explanation = response.choices[0].message.content

        # Update conversation history
        if hasattr(self, 'conversation_history'):
            self.conversation_history.append({
                'text': topic,
                'is_user': True,
                'timestamp': datetime.now().isoformat()
            })
            self.conversation_history.append({
                'text': explanation,
                'is_user': False,
                'timestamp': datetime.now().isoformat()
            })

        return JsonResponse({
            "messages": [explanation]
        }), self.session

    async def _handle_reset_context(self, intent_data):
        # Clear context
        self.session.pop('last_topic', None)
        self.session.pop('last_context', None)
        self.session.pop('current_test', None)
        self.lab_context = {'last_results': None, 'current_topic': None}
        await update_session(self.user_id, self.session)  # Ensure session update is persisted

        excluded_topic = intent_data.get('entities', {}).get('excluded_topic')
        response = f"I understand you don't want to talk about {excluded_topic if excluded_topic else 'the previous topic'}. "
        response += "What would you like to discuss instead? I can help with:\n"
        response += "- Your medical records\n"
        response += "- Scheduling appointments\n"
        response += "- Explaining lab results\n"
        response += "- General health information\n"
        response += "Or you can ask 'what can you do' to see all my capabilities."

        return [response], self.session
     
