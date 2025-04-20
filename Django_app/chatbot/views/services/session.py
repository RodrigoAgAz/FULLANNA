import logging
import json
from datetime import datetime, timezone, timedelta
import asyncio
import time
from redis import asyncio as aioredis
from contextlib import asynccontextmanager
from django.conf import settings
from .fhir_service import FHIRService
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class SessionManager:
    # In-memory session fallback storage with timestamps
    _memory_sessions: Dict[str, Dict] = {}
    
    def __init__(self):
        self._redis_client = None
        self._lock = None  # Initialize in async context
        self.session_timeout = timedelta(seconds=settings.SESSION_TTL_SECONDS)
        self.fhir_service = FHIRService()  # Using existing FHIRService
        self.redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')

    def _get_session_key(self, session_id: str) -> str:
        """Get consistent session key format"""
        return f"chat_session:{session_id}"
        
    def cleanup_expired_memory_sessions(self):
        """
        Remove in-memory sessions that have expired according to TTL
        This prevents memory leaks from abandoned sessions
        """
        now = time.time()
        expired_keys = []
        
        for session_id, session_data in SessionManager._memory_sessions.items():
            # Extract timestamp from session data
            last_interaction = session_data.get('last_interaction')
            if not last_interaction:
                # No timestamp, consider expired
                expired_keys.append(session_id)
                continue
                
            try:
                # Convert ISO timestamp to Unix time
                if isinstance(last_interaction, str):
                    last_time = datetime.fromisoformat(last_interaction.replace('Z', '+00:00'))
                    last_unix_time = last_time.timestamp()
                    
                    # Check if expired based on TTL
                    if now - last_unix_time > settings.SESSION_TTL_SECONDS:
                        expired_keys.append(session_id)
            except (ValueError, TypeError):
                # Invalid timestamp format, consider expired
                expired_keys.append(session_id)
        
        # Remove expired sessions
        for key in expired_keys:
            SessionManager._memory_sessions.pop(key, None)
            
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired memory sessions")

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
                if self._lock is None:
                    self._lock = asyncio.Lock()
                    
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
            logger.warning("Redis connection not available, using in-memory storage")
            yield None

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get existing session or create new one"""
        try:
            # Clean up expired memory sessions first
            self.cleanup_expired_memory_sessions()
            
            # Check in-memory sessions
            if session_id in SessionManager._memory_sessions:
                logger.info(f"Using in-memory session for {session_id}")
                return SessionManager._memory_sessions[session_id]
        
            async with self.get_redis() as redis:
                if redis is None:
                    logger.warning("Redis connection not available, using in-memory fallback")
                    # Check again for memory sessions
                    if session_id in SessionManager._memory_sessions:
                        return SessionManager._memory_sessions[session_id]
                    # No session found, create default
                    new_session = await self._create_or_verify_session(session_id)
                    SessionManager._memory_sessions[session_id] = new_session
                    return new_session
                
                session_key = self._get_session_key(session_id)
                try:
                    session_data = await redis.get(session_key)
                    if session_data:
                        parsed_session = json.loads(session_data)
                        # Store in memory for faster access
                        SessionManager._memory_sessions[session_id] = parsed_session
                        return parsed_session
                except Exception as e:
                    logger.error(f"Error reading session: {e}")
                    # Check memory fallback
                    if session_id in SessionManager._memory_sessions:
                        return SessionManager._memory_sessions[session_id]
                    raise
                
                # Create new session
                new_session = await self._create_or_verify_session(session_id)
                try:
                    await redis.set(
                        session_key,
                        json.dumps(new_session),
                        ex=settings.SESSION_TTL_SECONDS
                    )
                    # Store in memory too
                    SessionManager._memory_sessions[session_id] = new_session
                except Exception as e:
                    logger.error(f"Error saving new session: {e}")
                    # Still store in memory
                    SessionManager._memory_sessions[session_id] = new_session
                return new_session
                
        except Exception as e:
            logger.error(f"Session operation failed: {e}")
            raise
    
    async def update_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Update existing session"""
        try:
            # Update last interaction time
            session_data['last_interaction'] = datetime.now(timezone.utc).isoformat()
            
            async with self.get_redis() as redis:
                if redis is None:
                    # Redis not available, use in-memory storage
                    logger.warning("Redis connection not available, using in-memory storage")
                    # Store in memory
                    SessionManager._memory_sessions[session_id] = session_data
                    return
                
                # Store updated session using consistent key format
                session_key = self._get_session_key(session_id)
                await redis.set(
                    session_key,
                    json.dumps(session_data),
                    ex=settings.SESSION_TTL_SECONDS
                )
                # Update memory cache
                SessionManager._memory_sessions[session_id] = session_data
        except Exception as e:
            logger.error(f"Error updating session: {str(e)}")
            # Fall back to in-memory storage
            SessionManager._memory_sessions[session_id] = session_data

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
            # Update last interaction time
            session_data['last_interaction'] = datetime.now(timezone.utc).isoformat()
            
            # Update memory cache
            SessionManager._memory_sessions[session_id] = session_data
            
            async with self.get_redis() as redis:
                if redis is None:
                    return False
                
                await redis.set(
                    self._get_session_key(session_id),
                    json.dumps(session_data),
                    ex=settings.SESSION_TTL_SECONDS
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
    # Added basic validation to avoid sending None as updates
    if not session_id or not updates:
        logger.error("Invalid parameters for update_session: session_id or updates missing")
        return False
        
    # Create a new dict to avoid modifying the original
    safe_updates = {}
    for k, v in updates.items():
        if k and v is not None:  # Only include non-None values
            safe_updates[k] = v
    
    return await session_manager.update_session(session_id, safe_updates)

async def reset_session(session_id: str, preserve_patient: bool = True) -> Dict[str, Any]:
    return await session_manager.reset_session(session_id, preserve_patient)

async def save_session(session_id: str, session_data: Dict[str, Any]) -> bool:
    return await session_manager.save_session(session_id, session_data)