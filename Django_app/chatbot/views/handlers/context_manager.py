"""
chatbot/views/handlers/context_manager.py

This module manages conversation context for a HIPAA-compliant medical chatbot.
It supports threaded conversations, adaptive topic switching, incremental summarization,
and semantic retrieval while ensuring robust PHI redaction, local embedding generation,
and enhanced topic & fact extraction.
"""

import logging
logger = logging.getLogger(__name__)

import json
import re
from datetime import datetime
from typing import List, Dict, Any
import hashlib
import os
from dotenv import load_dotenv
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).resolve().parent.parent.parent)
sys.path.append(project_root)

from dotenv import load_dotenv
load_dotenv()

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')
django.setup()
import numpy as np
from django.conf import settings
from openai import AsyncOpenAI
load_dotenv()

import django
from asgiref.sync import sync_to_async
# Session update function (ensure this function handles encryption and secure storage)
from chatbot.views.services.session import update_session
logger.debug("Context manager module loaded")
# ---------------------------
# Initialize Global Components
# ---------------------------

# Initialize Microsoft Presidio Analyzer for PHI detection
try:
    from presidio_analyzer import AnalyzerEngine
    presidio_analyzer = AnalyzerEngine()
except ImportError:
    raise ImportError("Please install presidio-analyzer for robust PHI redaction.")

# Initialize spaCy with a medical model if available, otherwise fallback
try:
    import spacy
    nlp = spacy.load("en_core_web_lg")
except Exception as e:
    logging.warning("en_core_web_lg not found. Falling back to en_core_web_sm. Error: %s", e)
    import spacy
    nlp = spacy.load("en_core_web_sm")

# Initialize SentenceTransformer for generating real embeddings locally
try:
    from sentence_transformers import SentenceTransformer
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
except ImportError:
    raise ImportError("Please install sentence_transformers to generate embeddings.")

# Initialize a zero-shot classification pipeline from Hugging Face for topic classification
try:
    from transformers import pipeline
    topic_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
except ImportError:
    raise ImportError("Please install transformers to enable topic classification.")

logger = logging.getLogger(__name__)

# ---------------------------
# Utility Functions
# ---------------------------

def redact_sensitive_info(text: str) -> str:
    """
    Use Microsoft Presidio to detect and redact PHI in the text.
    Then apply additional PII redaction using our custom security module.
    """
    try:
        # First pass with Presidio for comprehensive PHI detection
        results = presidio_analyzer.analyze(text=text, language="en")
        for result in results:
            # Replace each detected entity with [REDACTED]
            text = text.replace(result.entity_text, "[REDACTED]")
            
        # Second pass with our custom redaction for general PII
        from chatbot.utils.security import redact_pii
        text = redact_pii(text)
    except Exception as e:
        logger.error(f"Error in PHI redaction: {str(e)}", exc_info=True)
        # Fall back to basic redaction if Presidio fails
        from chatbot.utils.security import redact_pii
        text = redact_pii(text)
    return text

def generate_embedding(text: str) -> np.ndarray:
    """
    Generate a real embedding vector for the text using SentenceTransformer.
    """
    # Ensure text is redacted before embedding to avoid storing raw PHI
    redacted_text = redact_sensitive_info(text)
    embedding = embedding_model.encode(redacted_text)
    return embedding

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.
    """
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))

def compute_hash(text: str) -> str:
    """
    Compute an MD5 hash of the given text.
    Useful for caching summaries.
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()

async def summarize_messages(messages: List[str], openai_client: AsyncOpenAI) -> str:
    """
    Use GPT-4-turbo (or similar) to generate a concise bullet-point summary.
    Redacts sensitive data before summarization.
    """
    if not messages:
        return ""

    # Redact PHI in each message and join them
    joined_messages = "\n".join(f"User: {redact_sensitive_info(m)}" for m in messages)
    
    system_prompt = (
        "You are an assistant that summarizes conversation context. "
        "Return a concise bullet list (max ~100 tokens) capturing key user info "
        "(symptoms, conditions, preferences) without including any sensitive data."
    )

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Conversation so far:\n{joined_messages}"}
    ]

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo",  # Adjust as needed
            messages=prompt,
            temperature=0.7,
            max_tokens=150
        )
        summary_text = response.choices[0].message.content.strip()
        return summary_text
    except Exception as e:
        logger.error(f"Error summarizing messages: {str(e)}", exc_info=True)
        return ""

def classify_topic(message: str) -> str:
    """
    Classify the topic of the message using a zero-shot classification pipeline.
    """
    # Expanded candidate labels to include explanation, screening, and prevention
    candidate_labels = ["scheduling", "medication", "symptoms", "explanation", "screening", "prevention", "general"]
    try:
        result = topic_classifier(message, candidate_labels)
        topic = result["labels"][0]
        return topic
    except Exception as e:
        logger.error(f"Error classifying topic: {str(e)}", exc_info=True)
        # Fallback to keyword matching with expanded options
        message_lower = message.lower()
        if "appointment" in message_lower or "schedule" in message_lower:
            return "scheduling"
        elif "medication" in message_lower or "prescription" in message_lower:
            return "medication"
        elif "symptom" in message_lower or "pain" in message_lower:
            return "symptoms"
        elif any(word in message_lower for word in ["explanation", "explain", "what is", "why do i need", "tell me about"]):
            return "explanation"
        elif any(word in message_lower for word in ["screening", "test", "should i get", "colonoscopy", "mammogram"]):
            return "screening"
        elif any(word in message_lower for word in ["prevent", "avoid", "reduce risk", "how to stop"]):
            return "prevention"
        else:
            return "general"

def extract_medical_facts(text: str) -> Dict[str, str]:
    """
    Use spaCy's NER to extract medical-related entities such as conditions and medications.
    """
    facts = {}
    try:
        doc = nlp(text)
        for ent in doc.ents:
            # You may refine this based on the entity labels your model produces.
            if ent.label_.lower() in ["condition", "disease", "symptom"]:
                facts["condition"] = ent.text
            elif ent.label_.lower() in ["medication", "drug"]:
                facts["medication"] = ent.text
    except Exception as e:
        logger.error(f"Error extracting medical facts: {str(e)}", exc_info=True)
    return facts

# ---------------------------
# ContextManager Class
# ---------------------------

class ContextManager:
    def __init__(self, user_id: str, session: Dict[str, Any], openai_client: AsyncOpenAI):
        self.user_id = user_id
        self.session = session
        self.openai_client = openai_client

        # Retrieve or initialize conversation data from the session.
        self.conversation_history = self.session.get("conversation_history", [])
        self.topic_summaries = self.session.get("topic_summaries", {})  # {topic: summary}
        self.embeddings = self.session.get("embeddings", {})  # {timestamp: embedding vector as list}
        # Cache summary hashes to avoid unnecessary API calls.
        self.summary_cache = self.session.get("summary_cache", {})

    async def add_message(self, user_id: str, message: str):
        """
        Add a new message to the conversation.
        Processes the message with robust PHI redaction, topic classification,
        and embedding generation.
        """
        topic = classify_topic(message)
        redacted_message = redact_sensitive_info(message)
        timestamp = datetime.now().isoformat()

        # Extract additional facts from the raw message using spaCy.
        extracted_facts = extract_medical_facts(message)

        # Encrypt the original message before storing
        from chatbot.utils.security import encrypt_message
        encrypted_message = encrypt_message(message)
        
        message_entry = {
            "message": redacted_message,            # Redacted version for storage
            "encrypted_message": encrypted_message, # Encrypted original message
            "is_user": True,
            "timestamp": timestamp,
            "topic": topic,
            "facts": extracted_facts
        }
        
        # Use redacted message for all logging
        logger.debug(f"Processing message: {redacted_message}")

        self.conversation_history.append(message_entry)
        self.session["conversation_history"] = self.conversation_history

        # Generate and store an embedding for the redacted message.
        embedding = generate_embedding(redacted_message)
        self.embeddings[timestamp] = embedding.tolist()  # Save as list for JSON serialization
        self.session["embeddings"] = self.embeddings

        # Update current_topic in session for proper follow-up question handling
        await self.update_current_topic(topic, {
            "facts": extracted_facts,
            "timestamp": timestamp
        })

        # Update the summary for the specific topic if necessary.
        await self._maybe_summarize_history(topic)

        logger.info(f"Added message for user {user_id} with topic '{topic}' at {timestamp}")
        await self.save_session()

    async def update_current_topic(self, topic_name: str, topic_data: Dict = None):
        """
        Update the current topic in the session to support follow-up question processing.
        This creates a properly structured current_topic that intent_service.py expects.
        
        Args:
            topic_name: String name of the topic (e.g., 'lab_results', 'symptoms')
            topic_data: Optional dictionary of additional metadata for the topic
        """
        if topic_data is None:
            topic_data = {}
        
        # Don't overwrite a specific topic with a generic one
        generic = {"general", "explanation", "followup", "unknown", ""}
        current = self.session.get("current_topic", {}).get("name", "")
        if topic_name in generic and current and current not in generic:
            logger.debug(f"Skipping generic topic '{topic_name}', keeping '{current}'")
            return
            
        # Map topic from classifier to intent service's expected topic types
        topic_type_mapping = {
            "scheduling": "appointment",
            "medication": "medication",
            "symptoms": "symptom_report",
            "general": "general",
            "explanation": "explanation",  # Map explanation topic to explanation type
            "screening": "explanation",    # Map screening topics to explanation type for now
            "prevention": "explanation",   # Prevention is also educational in nature
            # Add explicit mappings for symptom categories
            "back_pain": "symptom_report",
            "headache": "symptom_report", 
            "leg_pain": "symptom_report",
            "chest_pain": "symptom_report",
            "abdominal_pain": "symptom_report",
            "arm_pain": "symptom_report",
            "knee_pain": "symptom_report",
            "foot_pain": "symptom_report", 
            "hand_pain": "symptom_report",
            "ankle_pain": "symptom_report",
        }
        
        # Create a properly structured current_topic that intent_service.py expects
        current_topic = {
            'name': topic_name,
            'type': topic_type_mapping.get(topic_name, topic_name),
            'last_updated': datetime.now().isoformat()
        }
        
        # Add any additional metadata
        for key, value in topic_data.items():
            if key not in current_topic:
                current_topic[key] = value
        
        # Store in session
        self.session['current_topic'] = current_topic
        logger.info(f"Updated current topic to: {topic_name}")
        logger.info(f"Current topic structure: {current_topic}")
        
        # Debug logging
        logger.debug(f"Updated current_topic to {current_topic}")

    async def get_context(self, user_id: str, current_topic: str = "general") -> Dict[str, Any]:
        """
        Retrieve the current context for the conversation.
        Returns:
          - Topic-specific summary
          - Last N (default 10) messages matching the current topic
        """
        recent_messages = [msg for msg in self.conversation_history if msg.get("topic") == current_topic][-10:]
        summary = self.topic_summaries.get(current_topic, self.session.get("conversation_summary", ""))
        return {"summary": summary, "recent_messages": recent_messages}

    async def add_user_fact(self, user_id: str, fact_type: str, fact: str):
        """
        Add or update a user-specific fact (e.g., conditions, medications) in the session.
        """
        user_facts = self.session.get("user_facts", {}).get(fact_type, [])
        if fact not in user_facts:
            user_facts.append(fact)
            self.session.setdefault("user_facts", {})[fact_type] = user_facts
            logger.info(f"Added {fact_type} fact for user {user_id}: {fact}")
            await self.save_session()

    async def _build_gpt_prompt(self, user_input: str, current_topic: str = "general") -> str:
        """
        Build the system prompt for GPT including user facts and conversation context.
        """
        user_facts = self.session.get("user_facts", {})
        facts_str = "\n".join(f"- {k}: {v}" for k, v in user_facts.items())
        conversation_summary = self.topic_summaries.get(current_topic, self.session.get("conversation_summary", ""))

        system_prompt = f"""
You are a helpful, HIPAA-compliant medical assistant.
Known user facts:
{facts_str}

Summarized conversation (topic: '{current_topic}'):
{conversation_summary}

The user says: {user_input}
"""
        return system_prompt

    async def get_user_facts(self, user_id: str) -> Dict[str, List[str]]:
        """
        Retrieve stored user facts.
        """
        return self.session.get("user_facts", {})

    async def save_session(self):
        """
        Save the updated session.
        Ensure that the session backend is secure and encrypted.
        """
        try:
            # Ensure all session data is JSON serializable
            # Convert any numpy arrays or other non-serializable objects
            serializable_session = {}
            
            # Log key parts of the session we care about for debugging
            logger.info(f"Preparing to save session with current_topic: {self.session.get('current_topic')}")
            logger.debug(f"Current_topic before serialization: {self.session.get('current_topic')}")
            
            for key, value in self.session.items():
                if key == 'embeddings':
                    # Make sure embeddings are lists not numpy arrays
                    serializable_embeddings = {}
                    for timestamp, embedding in value.items():
                        if hasattr(embedding, 'tolist'):
                            serializable_embeddings[timestamp] = embedding.tolist()
                        else:
                            serializable_embeddings[timestamp] = embedding
                    serializable_session[key] = serializable_embeddings
                else:
                    serializable_session[key] = value
            
            # Double-check current_topic is properly included before saving
            if 'current_topic' in self.session and 'current_topic' not in serializable_session:
                serializable_session['current_topic'] = self.session['current_topic']
                logger.warning("Had to manually add current_topic to serializable session")
            
            logger.info(f"Session saved for user {self.user_id} at {datetime.now().isoformat()}")
            logger.debug(f"Current_topic in serializable session: {serializable_session.get('current_topic')}")
            
            # Save the session
            await update_session(self.user_id, serializable_session)
            logger.info("Session successfully updated")
            
        except Exception as e:
            logger.error(f"Error saving session: {str(e)}", exc_info=True)
            # Fall back to just saving without embeddings if there's an error
            try:
                session_copy = self.session.copy()
                if 'embeddings' in session_copy:
                    del session_copy['embeddings']
                await update_session(self.user_id, session_copy)
                logger.info("Session saved without embeddings due to serialization error")
            except Exception as e2:
                logger.error(f"Complete failure saving session: {str(e2)}", exc_info=True)

    async def _maybe_summarize_history(self, topic: str):
        """
        If the number of raw messages for a given topic exceeds a threshold,
        generate and cache a summary to reduce API calls and keep context lean.
        """
        MAX_RAW_MESSAGES = 10
        topic_messages = [msg for msg in self.conversation_history if msg.get("topic") == topic]
        if len(topic_messages) > MAX_RAW_MESSAGES:
            # Build a concatenated string of the messages to summarize.
            older_chunk = [msg["message"] for msg in topic_messages[:-MAX_RAW_MESSAGES]]
            combined_text = "\n".join(older_chunk)
            text_hash = compute_hash(combined_text)

            # Check if this summary is already cached.
            if self.summary_cache.get(topic) == text_hash:
                logger.info(f"Summary for topic '{topic}' is already up-to-date; skipping summarization.")
                return

            summary_text = await summarize_messages(older_chunk, self.openai_client)
            old_summary = self.topic_summaries.get(topic, "")
            combined_summary = f"{old_summary}\n{summary_text}".strip() if old_summary else summary_text
            self.topic_summaries[topic] = combined_summary
            self.session["topic_summaries"] = self.topic_summaries

            # Cache the hash for this topic summary.
            self.summary_cache[topic] = text_hash
            self.session["summary_cache"] = self.summary_cache

            # Prune older messages for this topic (retain only the last MAX_RAW_MESSAGES).
            recent_topic_messages = topic_messages[-MAX_RAW_MESSAGES:]
            # Remove all messages of this topic and add back the recent ones.
            self.conversation_history = [msg for msg in self.conversation_history if msg.get("topic") != topic] + recent_topic_messages
            self.session["conversation_history"] = self.conversation_history

            await self.save_session()
            logger.info(f"Summarized and pruned history for topic '{topic}' for user {self.user_id}")

    async def _extract_user_facts(self, message_text: str) -> Dict[str, str]:
        """
        Optionally extract key facts (e.g., conditions or medications) using spaCy.
        This method calls extract_medical_facts, which is a synchronous function.
        """
        try:
            # Use sync_to_async to properly wrap the synchronous function
            # This ensures the method correctly returns an awaitable result
            extract_medical_facts_async = sync_to_async(extract_medical_facts)
            facts = await extract_medical_facts_async(message_text)
            logger.info(f"Extracted facts: {facts}")
            return facts
        except Exception as e:
            logger.error(f"Error extracting user facts: {str(e)}", exc_info=True)
            return {}

    async def retrieve_similar_messages(self, current_input: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve semantically similar messages using embeddings.
        """
        current_embedding = generate_embedding(redact_sensitive_info(current_input))
        similarities = []
        for msg in self.conversation_history:
            msg_timestamp = msg.get("timestamp")
            msg_embedding_list = self.embeddings.get(msg_timestamp)
            if msg_embedding_list:
                msg_embedding = np.array(msg_embedding_list)
                similarity = cosine_similarity(current_embedding, msg_embedding)
                similarities.append((similarity, msg))
        similarities.sort(key=lambda x: x[0], reverse=True)
        top_messages = [msg for sim, msg in similarities[:top_n]]
        return top_messages

logger.debug("Context manager initialization complete")