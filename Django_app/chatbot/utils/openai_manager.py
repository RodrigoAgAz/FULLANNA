import logging
import asyncio
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

class OpenAIManager:
    """Centralized OpenAI client manager"""
    
    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the OpenAI client"""
        if self._initialized:
            return
            
        async with self._lock:
            if not self._initialized:
                try:
                    self._client = AsyncOpenAI(
                        api_key=settings.OPENAI_API_KEY,
                        timeout=30.0
                    )
                    self._initialized = True
                    logger.info("OpenAI client initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    raise
    
    @property
    async def client(self) -> AsyncOpenAI:
        """Get the OpenAI client, initializing if necessary"""
        if not self._initialized:
            await self.initialize()
        return self._client
    
    async def chat_completion(
        self,
        messages: list,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 1000,
        **kwargs
    ) -> Any:
        """Create a chat completion with error handling"""
        try:
            client = await self.client
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def detect_intent_with_ai(
        self,
        user_input: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Use OpenAI for intent detection"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are a medical chatbot intent classifier. Classify user messages into these intents:
- set_appointment: User wants to book/schedule an appointment
- show_appointments: User wants to view their appointments
- medical_record_query: User wants to see their medical records
- medical_info_query: User asks for medical information/education
- symptom_report: User reports specific symptoms
- issue_report: User reports health issues/problems
- lab_results_query: User asks about lab test results
- lab_results: User wants to view lab results
- capabilities: User asks what you can do
- explanation_query: User wants explanations about medical topics
- greeting: User says hello/hi
- condition_query: User asks about their medical conditions
- mental_health_query: User discusses mental health
- screening: User asks about health screenings
- unknown: Intent unclear

Return JSON: {"intent": "intent_name", "confidence": 0.0-1.0, "entities": {}}"""
                },
                {
                    "role": "user",
                    "content": f"Message: {user_input}\nContext: {context or {}}"
                }
            ]
            
            response = await self.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=150
            )
            
            import json
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"AI intent detection failed: {e}")
            return {
                "intent": "unknown",
                "confidence": 0.1,
                "entities": {}
            }
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._client:
            await self._client.close()
            self._client = None
            self._initialized = False

# Global instance
openai_manager = OpenAIManager()