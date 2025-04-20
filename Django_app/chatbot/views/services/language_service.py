# chatbot/views/services/language_service.py
import logging
import json
from langdetect import detect, DetectorFactory
from django.conf import settings
from django.core.cache import cache  # Redis cache backend
from openai import AsyncOpenAI  # Changed to AsyncOpenAI
import re
from ..utils.constants import OPENAI_MODEL
import hashlib

logger = logging.getLogger('chatbot')
logger.debug("Language service initialized")

class LanguageService:
    def __init__(self):
        DetectorFactory.seed = 0
        self.supported_languages = {
            'en': {'name': 'English', 'code': 'en'},
            'es': {'name': 'Spanish', 'code': 'es'}
        }
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)  # Changed to AsyncOpenAI
    
    async def detect_language(self, text):
        """Detect the language of the input text"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a language detector. Return JSON with language and translation if not English."},
                    {"role": "user", "content": f"Analyze: {text}\nReturn: " + '{"language": "en|es", "translated": "English translation if not English"}'}
                ]
            )
            try:
                result = json.loads(response.choices[0].message.content)
                return result.get('language', 'en').split('|')[0]
            except json.JSONDecodeError:
                logger.error("Failed to parse language detection response")
                return 'en'
        except Exception as e:
            logger.error(f"Error detecting language: {str(e)}")
            return 'en'
    
    def get_localized_message(self, message_key, lang_code='en'):
        """Get localized version of a message"""
        messages = {
            'emergency_text': {
                'en': '🚨 EMERGENCY: Seek immediate medical attention',
                'es': '🚨 EMERGENCIA: Busque atención médica inmediata'
            },
            'disclaimer': {
                'en': 'This is an automated assessment. Always consult a healthcare professional.',
                'es': 'Esta es una evaluación automatizada. Siempre consulte a un profesional de la salud.'
            }
        }
        return messages.get(message_key, {}).get(lang_code, messages[message_key]['en'])
    
    async def translate_text(self, text, target_lang='en'):
        """
        Translate text using OpenAI with Redis caching
        
        Uses a hash of the text and target language as the cache key.
        Caches translations for 90 days to reduce API costs.
        """
        if not text or target_lang == 'en':
            return text
            
        # Generate a cache key based on the text and target language
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        cache_key = f"trans:{target_lang}:{text_hash}"
        
        # Check cache first
        cached_translation = cache.get(cache_key)
        if cached_translation:
            logger.info(f"Using cached translation for {target_lang} (key: {cache_key[:10]}...)")
            return cached_translation

        try:
            # No cache hit, call the OpenAI API
            logger.info(f"Translation cache miss - calling API for {target_lang} text (key: {cache_key[:10]}...)")
            response = await self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": f"You are a translator. Translate the following text to {self.supported_languages[target_lang]['name']}, maintaining the same tone and meaning:"},
                    {"role": "user", "content": text}
                ],
                temperature=0.3
            )
            translation = response.choices[0].message.content.strip()
            
            # Cache the result for 90 days (60*60*24*90 = 7,776,000 seconds)
            cache.set(cache_key, translation, 60*60*24*90)
            
            # Audit the translation (but not the content for privacy)
            from audit.utils import log_event
            log_event(
                actor="system", 
                action="translation.new",
                resource=f"language.{target_lang}",
                meta={"chars": len(text), "cache_key": cache_key}
            )
            
            return translation
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return text
            
    async def _gpt_translate(self, text, target_lang):
        """
        Internal method to perform the actual OpenAI translation
        Used by the cached translate_text method
        """
        try:
            response = await self.openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": f"You are a translator. Translate the following text to {self.supported_languages[target_lang]['name']}, maintaining the same tone and meaning:"},
                    {"role": "user", "content": text}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"GPT translation error: {str(e)}")
            return text

class LanguageHandler:
    def __init__(self):
        self.language_service = LanguageService()
    
    async def process_multilingual(self, text):
        try:
            detected_lang = await self.language_service.detect_language(text)
            needs_translation = detected_lang != 'en'
            
            if needs_translation:
                english_text = await self.language_service.translate_text(text, 'en')
            else:
                english_text = text
                
            return english_text, needs_translation
        except Exception as e:
            logger.error(f"Error in process_multilingual: {str(e)}")
            return text, False
            
    async def translate_response(self, response, needs_translation, target_lang):
        """Translate the response if needed"""
        try:
            if not needs_translation or target_lang == 'en':
                return response

            if isinstance(response, str):
                return await self.language_service.translate_text(response, target_lang)
                
            if isinstance(response, dict) and 'messages' in response:
                translated_messages = []
                for message in response['messages']:
                    try:
                        translated_text = await self.language_service.translate_text(
                            message, 
                            target_lang
                        )
                        translated_messages.append(translated_text)
                    except Exception as e:
                        logger.error(f"Error translating message: {str(e)}")
                        translated_messages.append(message)
                    
                response['messages'] = translated_messages
                
            return response
            
        except Exception as e:
            logger.error(f"Error in translate_response: {str(e)}")
            return response
    async def translate_to_english(self, text):
      """Translate text to English"""
      if not text:
          return text

      try:
          _, needs_translation = await self.process_multilingual(text)
          if needs_translation:
              return await self.language_service.translate_text(text, 'en')
          return text
      except Exception as e:
          logger.error(f"Error translating to English: {str(e)}")
          return text
            
logger.debug("Language service initialization complete")