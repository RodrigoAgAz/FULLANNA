import logging
import json
from datetime import datetime, timezone, timedelta
import asyncio
from redis import asyncio as aioredis
from contextlib import asynccontextmanager
from django.conf import settings
from .fhir_service import FHIRService
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)
print ("38")
class SessionManager:
    def __init__(self):
        self._redis_client = None
        self._lock = None  # Initialize in async context
        self.session_timeout = timedelta(minutes=30)
        self.fhir_service = FHIRService()  # Using existing FHIRService
        self.redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')

    def _get_session_key(self, session_id: str) -> str:
        """Get consistent session key format"""
        return f"chat_session:{session_id}"

    async def initialize(self):
        """Initialize session manager for ASGI application"""
        self._lock = asyncio.Lock()
        await self._initialize_redis()

    async def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            if self._redis_client is None:
                self._redis_client = await aioredis.from_url(
                    self.redis_url,
                    encoding='utf-8',
                    decode_responses=True
                )
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            self._redis_client = None

    async def cleanup(self):
        """Cleanup session manager resources"""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

    @asynccontextmanager
    async def get_redis(self):
        """Get Redis connection with proper error handling"""
        if self._redis_client is None:
            try:
                async with self._lock:
                    if self._redis_client is None:
                        await self._initialize_redis()
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self._redis_client = None
        
        if self._redis_client is not None:
            try:
                yield self._redis_client
            except Exception as e:
                logger.error(f"Redis operation failed: {e}")
                self._redis_client = None
                raise  # Re-raise to ensure proper error handling
        else:
            yield None

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get existing session or create new one"""
        try:
            async with self.get_redis() as redis:
                if redis is None:
                    logger.warning("Redis connection not available, using in-memory fallback")
                    return self._create_default_session(session_id)
                
                session_key = self._get_session_key(session_id)
                try:
                    print("hello inside get_session function, before redis.get")
                    session_data = await redis.get(session_key)
                    print("hello inside get_session function, after redis.get")
                    if session_data:
                        return json.loads(session_data)
                except Exception as e:
                    logger.error(f"Error reading session: {e}")
                    raise
                
                # Create new session
                new_session = await self._create_or_verify_session(session_id)  # Fixed with await
                try:
                    await redis.set(
                        session_key,
                        json.dumps(new_session),
                        ex=int(self.session_timeout.total_seconds())
                    )
                except Exception as e:
                    logger.error(f"Error saving new session: {e}")
                    raise
                return new_session
                
        except Exception as e:
            logger.error(f"Session operation failed: {e}")
            raise

    async def update_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Update existing session"""
        try:
            async with self.get_redis() as redis:
                if redis is None:
                    logger.warning("Redis connection not available, session update skipped")
                    return
                
                # Update last interaction time
                session_data['last_interaction'] = datetime.now(timezone.utc).isoformat()
                
                # Store updated session using consistent key format
                session_key = self._get_session_key(session_id)
                await redis.set(
                    session_key,
                    json.dumps(session_data),
                    ex=int(self.session_timeout.total_seconds())
                )
        except Exception as e:
            logger.error(f"Error updating session: {str(e)}")
            # Log error but don't raise to maintain compatibility with existing code

    async def reset_session(self, session_id: str, preserve_patient: bool = True) -> Dict[str, Any]:
        """Reset session while optionally preserving patient data"""
        try:
            current_session = await self.get_session(session_id)
            patient_data = current_session.get('patient') if preserve_patient else None
            
            new_session = self._create_default_session(session_id)
            if patient_data:
                new_session['patient'] = patient_data
            
            await self.save_session(session_id, new_session)
            return new_session
            
        except Exception as e:
            logger.error(f"Error resetting session: {e}")
            return self._create_default_session(session_id)

    async def save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Save complete session data"""
        try:
            async with self.get_redis() as redis:
                if redis is None:
                    return False
                
                session_data['last_interaction'] = datetime.now(timezone.utc).isoformat()
                await redis.setex(
                    f"chat_session:{session_id}",
                    int(self.session_timeout.total_seconds()),
                    json.dumps(session_data)
                )
                return True
                
        except aioredis.RedisError as e:
            logger.error(f"Redis error saving session: {e}")
            return False
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            return False

    async def _create_or_verify_session(self, session_id: str) -> Dict[str, Any]:
        """Creates a new session and verifies patient data if email provided"""
        session = self._create_default_session(session_id)
        
        # Verify patient if session_id looks like an email
        if '@' in session_id:
            try:
                patient_data = await self.fhir_service.get_patient_by_email(session_id)
                if patient_data:
                    logger.info(f"Found patient data for {session_id}")
                    session['patient'] = patient_data
            except Exception as e:
                logger.error(f"Error verifying patient: {e}")
        
        return session

    def _create_default_session(self, session_id: str) -> Dict[str, Any]:
        """Create a default session with all required fields"""
        return {
            'id': session_id,
            'greeted': False,
            'booking_state': None,
            'cancellation_options': None,
            'requested_datetime': None,
            'last_interaction': datetime.now(timezone.utc).isoformat(),
            'verified': False,
            'patient': None
        }

    async def _verify_patient(self, session_id):
        try:
            patient_data = await self.fhir_service.get_patient_by_email(session_id)
            if patient_data:
                return patient_data
            return None
        except Exception as e:
            logger.error(f"Error verifying patient: {str(e)}")
            return None

    async def verify_patient(self, session_id: str) -> bool:
        """Verify patient exists in FHIR"""
        try:
            patient_data = await self.fhir_service.get_patient_by_email(session_id)
            if patient_data:
                self.session['patient'] = patient_data
                self.session['verified'] = True
                return True
            return False
        except Exception as e:
            logger.error(f"Error verifying patient: {str(e)}")
            return False

# Global instance
session_manager = SessionManager()

# For backwards compatibility with existing imports
async def get_session(session_id: str) -> Dict[str, Any]:
    return await session_manager.get_session(session_id)

async def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
    return await session_manager.update_session(session_id, updates)

async def reset_session(session_id: str, preserve_patient: bool = True) -> Dict[str, Any]:
    return await session_manager.reset_session(session_id, preserve_patient)

async def save_session(session_id: str, session_data: Dict[str, Any]) -> bool:
    return await session_manager.save_session(session_id, session_data)
print ("39")