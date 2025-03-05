# utils.py
from django.conf import settings
from openai import OpenAI
import redis
import logging

from fhir_client_module import FHIRClient

# Configure logging
logger = logging.getLogger('chatbot')

# Initialize shared clients
fhir_client = FHIRClient(base_url=settings.FHIR_SERVER_URL)
redis_client = redis.StrictRedis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Shared utility functions
def get_resource_name(resource):
    """Shared utility to extract name from FHIR resource"""
    if 'name' in resource and len(resource['name']) > 0:
        name_entry = resource['name'][0]
        if 'given' in name_entry and 'family' in name_entry:
            given = " ".join(name_entry.get('given', []))
            family = name_entry.get('family', '')
            return f"{given} {family}".strip()
        elif 'text' in name_entry and name_entry.get('text'):
            return name_entry.get('text').strip()
    return 'Unknown'