"""
Debug script to trace what's happening during ChatHandler initialization
"""
import os
import sys
import django
import inspect
import asyncio

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')
django.setup()

# Mock missing modules
import sys
from unittest.mock import MagicMock

# Mock presidio_analyzer
class MockPresidioAnalyzer:
    class AnalyzerEngine:
        def analyze(self, *args, **kwargs):
            return []
        def __init__(self, *args, **kwargs):
            pass

sys.modules['presidio_analyzer'] = MockPresidioAnalyzer

# Mock spacy
class MockSpacy:
    def load(self, *args, **kwargs):
        return MagicMock()

sys.modules['spacy'] = MockSpacy()

# Mock sentence_transformers
class MockSentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass
    def encode(self, *args, **kwargs):
        import numpy as np
        return np.zeros(10)  # Return a dummy embedding

class MockSentenceTransformers:
    SentenceTransformer = MockSentenceTransformer

sys.modules['sentence_transformers'] = MockSentenceTransformers

# Mock transformers
class MockTransformers:
    def pipeline(self, *args, **kwargs):
        def classifier(*args, **kwargs):
            return {"labels": ["general"], "scores": [0.9]}
        return classifier

sys.modules['transformers'] = MockTransformers()

# Now we can import ChatHandler and patch the translate_to_english method
from chatbot.views.handlers.chat_handler import ChatHandler

# Save the original method
original_translate_to_english = ChatHandler.translate_to_english

# Replace with a non-async version that doesn't return a coroutine
def patched_translate_to_english(self, text):
    print(f"PATCHED translate_to_english called with: {text}")
    return text  # Simply return the original text

# Apply the patch
ChatHandler.translate_to_english = patched_translate_to_english

async def main():
    """Test ChatHandler initialization"""
    print("Starting debug script")
    
    # Create a mock session
    session_data = {
        'user_id': 'test_user',
        'phone_number': '1234567890',
        'patient': None,
        'conversation_history': []
    }
    
    user_message = "Hello, this is a test"
    user_id = "test_user"
    
    try:
        print("Creating ChatHandler instance")
        handler = ChatHandler(session_data, user_message, user_id)
        print("ChatHandler instance created successfully")
        
        print("Initializing ChatHandler")
        await handler.initialize()
        print("ChatHandler initialized successfully")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        # Restore original method
        ChatHandler.translate_to_english = original_translate_to_english
    
    print("Debug script completed")

if __name__ == "__main__":
    asyncio.run(main())