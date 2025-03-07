"""
Custom ASGI application that directly maps chat endpoint to our handler
"""
import os
import json
from django.http import JsonResponse
from django.core.asgi import get_asgi_application

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')

# Get the default Django ASGI application
django_application = get_asgi_application()

# Custom chat handler
async def custom_chat_handler(scope, receive, send):
    """Custom handler for chat endpoint"""
    
    if scope["type"] == "http" and scope["path"] == "/chatbot/chat/":
        print("CUSTOM: Handling chat request")
        
        # Process the request
        request_body = b""
        while True:
            message = await receive()
            request_body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        
        # Parse the request body
        try:
            data = json.loads(request_body)
            user_id = data.get("user_id", "unknown")
            user_message = data.get("message", "")
            
            # Send a test response
            response = {
                "response": f"Custom handler processed: '{user_message}' from user {user_id}",
                "handler": "custom_asgi.py"
            }
            
            # Send a response back
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    [b"content-type", b"application/json"],
                ],
            })
            
            await send({
                "type": "http.response.body",
                "body": json.dumps(response).encode(),
            })
            return
        except Exception as e:
            print(f"CUSTOM: Error handling request: {str(e)}")
            # On error, let Django handle it
            pass
    
    # For all other paths, use the default Django application
    await django_application(scope, receive, send)

# ASGI application to be served by Uvicorn
application = custom_chat_handler