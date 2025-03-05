import asyncio
import json
import os
import sys
import logging
import django
from django.conf import settings

# Add the Django_app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')
django.setup()

from chatbot.views.services.intent_service import detect_intent

# Configure logging for better clarity
logging.basicConfig(level=logging.DEBUG)

async def run_tests():
    # A variety of test inputs simulating different user queries:
    test_messages = [
        "I would like to book an appointment next Monday at 2pm",
        "Show me my upcoming appointments",
        "I have severe chest pain and difficulty breathing",
        "What are the side effects of my current medication?",
        "Can I see my medical records?",
        "Explain my blood test results from last month",
        "How do I manage my diabetes?",
        "I want to cancel my appointment on December 9th",
        "What screenings should I get at age 45?",
        "help",
        "delete context"
    ]

    # Context simulation
    dummy_context = {
        'booking_state': None,
        'last_intent': None,
        'conversation_history': []
    }

    for message in test_messages:
        print(f"\n--- Testing message: '{message}' ---")
        intent_data = await detect_intent(message, dummy_context)
        print("Detected Intent Data:")
        print(json.dumps(intent_data, indent=2))

if __name__ == '__main__':
    asyncio.run(run_tests())