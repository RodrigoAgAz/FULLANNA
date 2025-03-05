"""
Sync wrapper for async chat endpoint
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import asyncio
import inspect
from asgiref.sync import async_to_sync
from chatbot.views.services.session import get_session
from chatbot.views.handlers.chat_handler import ChatHandler

# Async implementation - will be called by the sync wrapper
async def async_handle_chat(request_body, request_method):
    """Async implementation of chat handling"""
    print("ASYNC-HANDLE-1: Starting async chat handling")
    
    try:
        # Parse request data
        data = json.loads(request_body)
        user_id = data.get('user_id')
        user_message = data.get('message', '')
        print(f"ASYNC-HANDLE-2: User id={user_id}, message={user_message}")
        
        # Get session and initialize handler
        session_data = await get_session(user_id)
        handler = ChatHandler(session_data, user_message, user_id)
        await handler.initialize()
        print("ASYNC-HANDLE-3: Handler initialized")
        
        # Process message
        result = await handler.handle_message()
        print(f"ASYNC-HANDLE-4: Got result type={type(result)}")
        
        # Process the result
        if isinstance(result, tuple) and len(result) == 2:
            response, updated_session = result
        else:
            response = result
        
        # Ensure we return a dict that can be converted to JsonResponse
        if isinstance(response, dict):
            print("ASYNC-HANDLE-5: Result is a dict")
            return response
        elif hasattr(response, 'content'):
            print("ASYNC-HANDLE-6: Result has content attribute, converting to dict")
            try:
                return json.loads(response.content)
            except:
                return {"messages": ["Error converting response to dict"]}
        else:
            print(f"ASYNC-HANDLE-7: Unexpected response type {type(response)}")
            return {"messages": ["Unexpected response type"]}
            
    except Exception as e:
        print(f"ASYNC-HANDLE-ERROR: Error: {str(e)}")
        import traceback
        print(f"ASYNC-HANDLE-ERROR-TRACE: {traceback.format_exc()}")
        return {"messages": [f"Error: {str(e)}"]}

# Synchronous view that wraps the async implementation
@csrf_exempt
def sync_chat_view(request):
    """Synchronous wrapper around async chat handling"""
    print("SYNC-WRAPPER-1: Starting sync wrapper")
    
    try:
        # Read the request body
        request_body = request.body.decode('utf-8')
        request_method = request.method
        print(f"SYNC-WRAPPER-2: Request method={request_method}, body length={len(request_body)}")
        
        # Call the async implementation using async_to_sync
        print("SYNC-WRAPPER-3: Calling async implementation")
        response_data = async_to_sync(async_handle_chat)(request_body, request_method)
        print(f"SYNC-WRAPPER-4: Got response_data type={type(response_data)}")
        
        # Return a JsonResponse
        print("SYNC-WRAPPER-5: Creating JsonResponse")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"SYNC-WRAPPER-ERROR: Error: {str(e)}")
        import traceback
        print(f"SYNC-WRAPPER-ERROR-TRACE: {traceback.format_exc()}")
        return JsonResponse({"messages": [f"Error: {str(e)}"]})