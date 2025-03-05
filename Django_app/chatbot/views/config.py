from django.conf import settings
from openai import AsyncOpenAI
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
import logging
from .utils.constants import LOG_FORMAT, LOG_LEVEL, SESSION_EXPIRY_SECONDS
import openai
from fhirclient import client
from fhirclient.server import FHIRServer

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger('chatbot')

class Config:
    def __init__(self):
        self._fhir_client = None
        self._async_fhir_client = None
        self._redis_client = None
        self._async_redis_client = None
        self._openai_client = None
        self.initialize_clients()

    def initialize_clients(self):
        """Initialize all client connections"""
        try:
            # Initialize FHIR client
            settings_dict = {
                'app_id': 'anna_chatbot',
                'api_base': settings.FHIR_SERVER_URL
            }
            self._fhir_client = client.FHIRClient(settings=settings_dict)
            logger.info("FHIR client initialized successfully")

            # Initialize Redis clients - both sync and async
            self._redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            self._async_redis_client = AsyncRedis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            self._redis_client.ping()  # Test connection
            logger.info("Redis clients initialized successfully")
            
            # Initialize OpenAI client
            self._openai_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=60.0
            )
            logger.info("OpenAI client initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing clients: {str(e)}")
            raise

    async def get_async_fhir_client(self):
        """Get async FHIR server with lazy initialization"""
        if not self._async_fhir_client:
            settings_dict = {
                'app_id': 'anna_chatbot',
                'api_base': settings.FHIR_SERVER_URL
            }
            smart = client.FHIRClient(settings=settings_dict)
            self._async_fhir_client = smart.server
        return self._async_fhir_client

    def get_fhir_client(self):
        """Get synchronous FHIR server with lazy initialization"""
        if not self._fhir_client:
            settings_dict = {
                'app_id': 'anna_chatbot',
                'api_base': settings.FHIR_SERVER_URL
            }
            smart = client.FHIRClient(settings=settings_dict)
            self._fhir_client = smart.server
        return self._fhir_client

    def get_redis_client(self):
        """Get synchronous Redis client with lazy initialization"""
        if not self._redis_client:
            self._redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
        return self._redis_client

    def get_async_redis_client(self):
        """Get asynchronous Redis client with lazy initialization"""
        if not self._async_redis_client:
            self._async_redis_client = AsyncRedis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
        return self._async_redis_client
        
    def get_openai_client(self):
        """Get OpenAI client with lazy initialization"""
        if not self._openai_client:
            self._openai_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=60.0
            )
        return self._openai_client

    @property
    def fhir_client(self):
        """Property accessor for FHIR client"""
        return self.get_fhir_client()

    @property
    def redis_client(self):
        """Property accessor for Redis client"""
        return self.get_redis_client()

    @property
    def async_redis_client(self):
        """Property accessor for asynchronous Redis client"""
        return self.get_async_redis_client()

    @property
    def openai_client(self):
        """Property accessor for OpenAI client"""
        return self.get_openai_client()

    def reset_clients(self):
        """Reset all clients - useful for testing or error recovery"""
        self._fhir_client = None
        self._redis_client = None 
        self._async_redis_client = None
        self._openai_client = None
        self.initialize_clients()

# Add to existing config
INTENT_CONFIDENCE_THRESHOLDS = {
    # ... existing thresholds ...
    'lab_results': 0.8,
    'lab_query': 0.7
}

LAB_RESULT_CACHE_DURATION = 3600  # Cache lab results for 1 hour

# Create singleton instance
config = Config()