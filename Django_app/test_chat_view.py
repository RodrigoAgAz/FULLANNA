# Django_app/chatbot/management/commands/test_chat_view.py
from django.core.management.base import BaseCommand
from chatbot.views.api.endpoints import chat  # Import your chat view
from django.http import HttpRequest
import asyncio

class Command(BaseCommand):
    help = 'Tests the chat view function directly'

    def handle(self, *args, **options):
        print("--- Testing chat view function DIRECTLY ---")
        
        # Create a mock HttpRequest (minimal for testing)
        request = HttpRequest()
        request.method = 'POST'  # Assuming your chat view is for POST requests

        try:
            # Call the chat view function DIRECTLY (as a coroutine)
            loop = asyncio.get_event_loop()
            response = loop.run_until_complete(chat(request))

            print("\n--- Chat View Function Response: ---")
            print(f"Type of response: {type(response)}") # Debug: Check response type
            print(f"Response Content: {response.content.decode()}") # Decode content for printing

        except Exception as e:
            print("\n--- Error during chat view function execution: ---")
            import traceback
            traceback.print_exc()
