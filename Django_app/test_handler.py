import asyncio
import os
import django
import sys

# Set up Django
sys.path.append('/Users/rodrigoagag/Desktop/ANNA')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')
django.setup()

from chatbot.views.handlers.chat_handler import ChatHandler

async def test_handler():
    print("Starting test...")
    session_data = {'conversation_history': []}
    
    print("Creating handler...")
    handler = ChatHandler(session_data, "Hello")
    
    print("Handler created, now initializing...")
    await handler.initialize()
    
    print("Handler initialized successfully.")
    return handler

if __name__ == "__main__":
    asyncio.run(test_handler())