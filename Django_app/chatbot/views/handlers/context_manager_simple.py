"""
Simplified Context Manager for ANNA
Focused on core conversation tracking without heavy ML dependencies
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SimpleContextManager:
    """Lightweight context manager for conversation tracking"""
    
    def __init__(self):
        self.max_history = 10  # Keep last 10 interactions
        
    def update_conversation_context(
        self, 
        session_data: Dict[str, Any], 
        user_message: str, 
        bot_response: str, 
        intent: str,
        entities: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Update conversation context with new interaction"""
        try:
            # Initialize conversation history if not exists
            if 'conversation_history' not in session_data:
                session_data['conversation_history'] = []
            
            # Add new interaction
            interaction = {
                'timestamp': datetime.now().isoformat(),
                'user_message': user_message,
                'bot_response': bot_response,
                'intent': intent,
                'entities': entities or {}
            }
            
            session_data['conversation_history'].append(interaction)
            
            # Keep only recent history
            if len(session_data['conversation_history']) > self.max_history:
                session_data['conversation_history'] = session_data['conversation_history'][-self.max_history:]
            
            # Update current topic based on intent
            session_data['current_topic'] = self._extract_current_topic(intent, entities)
            
            # Update user facts
            session_data['user_facts'] = self._update_user_facts(session_data.get('user_facts', {}), user_message, intent, entities)
            
            logger.debug(f"Updated context: current_topic={session_data['current_topic']}")
            return session_data
            
        except Exception as e:
            logger.error(f"Error updating conversation context: {e}")
            return session_data
    
    def _extract_current_topic(self, intent: str, entities: Optional[Dict] = None) -> Dict[str, Any]:
        """Extract current topic from intent and entities"""
        entities = entities or {}
        
        topic_mapping = {
            'lab_results_query': {
                'type': 'lab_result',
                'name': entities.get('topic', 'lab results')
            },
            'lab_results': {
                'type': 'lab_results',
                'name': entities.get('test_name', 'lab results')
            },
            'symptom_report': {
                'type': 'symptom_report',
                'name': entities.get('symptom_category', 'symptoms')
            },
            'issue_report': {
                'type': 'issue_report',
                'name': entities.get('symptom_description', 'health issue')
            },
            'medical_info_query': {
                'type': 'medical_info',
                'name': entities.get('topic', 'medical information')
            },
            'explanation_query': {
                'type': 'explanation',
                'name': entities.get('topic', 'explanation')
            },
            'set_appointment': {
                'type': 'appointment',
                'name': 'appointment booking'
            },
            'show_appointments': {
                'type': 'appointment',
                'name': 'appointment viewing'
            },
            'medical_record_query': {
                'type': 'medical_record',
                'name': 'medical records'
            },
            'condition_query': {
                'type': 'condition',
                'name': 'medical conditions'
            },
            'mental_health_query': {
                'type': 'mental_health',
                'name': 'mental health'
            },
            'screening': {
                'type': 'screening',
                'name': 'health screening'
            }
        }
        
        return topic_mapping.get(intent, {
            'type': 'general',
            'name': intent
        })
    
    def _update_user_facts(
        self, 
        current_facts: Dict[str, Any], 
        user_message: str, 
        intent: str, 
        entities: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Update user facts based on conversation"""
        entities = entities or {}
        
        # Extract facts based on intent
        if intent == 'symptom_report' or intent == 'issue_report':
            if 'symptoms' not in current_facts:
                current_facts['symptoms'] = []
            symptom_desc = entities.get('symptom_description', user_message)
            if symptom_desc not in current_facts['symptoms']:
                current_facts['symptoms'].append(symptom_desc)
        
        elif intent == 'medical_info_query':
            if 'interests' not in current_facts:
                current_facts['interests'] = []
            topic = entities.get('topic', '')
            if topic and topic not in current_facts['interests']:
                current_facts['interests'].append(topic)
        
        elif intent == 'lab_results_query':
            if 'lab_interests' not in current_facts:
                current_facts['lab_interests'] = []
            topic = entities.get('topic', '')
            if topic and topic not in current_facts['lab_interests']:
                current_facts['lab_interests'].append(topic)
        
        # Update last interaction time
        current_facts['last_updated'] = datetime.now().isoformat()
        
        return current_facts
    
    def get_context_summary(self, session_data: Dict[str, Any]) -> str:
        """Get a summary of current conversation context"""
        try:
            history = session_data.get('conversation_history', [])
            current_topic = session_data.get('current_topic', {})
            
            if not history:
                return "No previous conversation."
            
            # Get recent interactions
            recent_intents = [h.get('intent', 'unknown') for h in history[-3:]]
            
            summary_parts = []
            
            if current_topic:
                summary_parts.append(f"Current topic: {current_topic.get('name', 'unknown')}")
            
            if recent_intents:
                summary_parts.append(f"Recent intents: {', '.join(recent_intents)}")
            
            return " | ".join(summary_parts) if summary_parts else "General conversation"
            
        except Exception as e:
            logger.error(f"Error generating context summary: {e}")
            return "Context unavailable"
    
    def reset_context(self, session_data: Dict[str, Any], preserve_patient: bool = True) -> Dict[str, Any]:
        """Reset conversation context"""
        try:
            # Clear conversation history
            session_data['conversation_history'] = []
            session_data['current_topic'] = {}
            session_data['user_facts'] = {}
            
            logger.info("Conversation context reset")
            return session_data
            
        except Exception as e:
            logger.error(f"Error resetting context: {e}")
            return session_data

# Global instance
context_manager = SimpleContextManager()

# Backward compatibility functions
async def update_conversation_context(session_data, user_message, bot_response, intent, entities=None):
    """Backward compatibility wrapper"""
    return context_manager.update_conversation_context(
        session_data, user_message, bot_response, intent, entities
    )

async def get_context_summary(session_data):
    """Backward compatibility wrapper"""
    return context_manager.get_context_summary(session_data)

async def reset_context(session_data, preserve_patient=True):
    """Backward compatibility wrapper"""
    return context_manager.reset_context(session_data, preserve_patient)