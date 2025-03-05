"""
Extremely simplified chat endpoint for testing
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import asyncio
import json

@csrf_exempt
async def minimal_chat(request):
    """Minimal async chat endpoint, doing just enough to test async functionality"""
    print("MINIMAL-CHAT-1: Starting minimal chat view")
    
    try:
        # Read request body
        print("MINIMAL-CHAT-2: Reading request body")
        body = await request.read()
        print(f"MINIMAL-CHAT-3: Request body: {body}")
        
        # Parse JSON
        print("MINIMAL-CHAT-4: Parsing JSON")
        try:
            data = json.loads(body)
            user_message = data.get('message', '')
            print(f"MINIMAL-CHAT-5: User message: {user_message}")
        except json.JSONDecodeError:
            user_message = "No valid message provided"
            print(f"MINIMAL-CHAT-ERROR: JSON decode error")
        
        # Simulate a small async delay
        print("MINIMAL-CHAT-6: Simulating async work")
        await asyncio.sleep(0.1)
        print("MINIMAL-CHAT-7: Async work complete")
        
        # Create response
        print("MINIMAL-CHAT-8: Creating response")
        response = JsonResponse({
            "messages": [f"You said: {user_message}"]
        })
        
        # Return response
        print("MINIMAL-CHAT-9: Returning response")
        return response
        
    except Exception as e:
        print(f"MINIMAL-CHAT-ERROR: Exception: {str(e)}")
        import traceback
        print(f"MINIMAL-CHAT-ERROR-TRACE: {traceback.format_exc()}")
        return JsonResponse({
            "messages": ["Sorry, something went wrong."]
        })