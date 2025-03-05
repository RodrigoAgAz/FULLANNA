import os
import sys
import json
import asyncio
from unittest.mock import MagicMock, patch

# Add the Django app directory to sys.path
sys.path.append('/Users/rodrigoagag/Desktop/ANNA/Django_app')

# Mock required modules before importing Django
sys.modules['presidio_analyzer'] = MagicMock()
sys.modules['presidio_analyzer.AnalyzerEngine'] = MagicMock()
sys.modules['spacy'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['transformers'] = MagicMock()
sys.modules['spacy.load'] = MagicMock()

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')

# Import Django and setup
import django
django.setup()

# Define minimal classes to substitute for the missing modules
class MockPresidioAnalyzer:
    class AnalyzerEngine:
        def analyze(self, *args, **kwargs):
            return []

class MockSpacy:
    @staticmethod
    def load(*args, **kwargs):
        return MagicMock()

class MockSentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass
    def encode(self, *args, **kwargs):
        import numpy as np
        return np.zeros(10)

# Replace the mocks with our minimal implementations
sys.modules['presidio_analyzer'] = MockPresidioAnalyzer
sys.modules['spacy'] = MockSpacy()

# Apply the patches
print("Applying patches...")
with patch('chatbot.views.handlers.context_manager.presidio_analyzer', MockPresidioAnalyzer), \
     patch('chatbot.views.handlers.context_manager.spacy', MockSpacy()), \
     patch('chatbot.views.handlers.context_manager.SentenceTransformer', MockSentenceTransformer), \
     patch('chatbot.views.handlers.context_manager.pipeline', MagicMock()):
    
    # Now import the modules we need
    print("Importing modules...")
    from chatbot.views.services.session import get_session
    from chatbot.views.handlers.chat_handler import ChatHandler

    async def test_chat():
        print("Starting test_chat()")
        user_id = "test_user"
        user_message = "Hello, how are you?"
        
        try:
            print(f"Getting session for user {user_id}")
            session_data = await get_session(user_id)
            print(f"Session data type: {type(session_data)}")
            
            print("Creating ChatHandler")
            handler = ChatHandler(session_data, user_message, user_id)
            print("Created ChatHandler successfully")
            
            print("Initializing handler")
            await handler.initialize()
            print("Handler initialized successfully")
            
            print("Calling handle_message")
            result = await handler.handle_message()
            print(f"handle_message result: {result}")
            print(f"handle_message result type: {type(result)}")
            
            print("Test completed successfully")
        except Exception as e:
            print(f"Error in test_chat: {e}")
            import traceback
            print(traceback.format_exc())

    if __name__ == "__main__":
        print("Starting test script")
        asyncio.run(test_chat())
        print("Test script completed")
