"""
New implementation of the chat endpoint
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import logging
import inspect
import traceback
from asgiref.sync import sync_to_async

from chatbot.views.services.session import get_session
from chatbot.views.handlers.chat_handler import ChatHandler

logger = logging.getLogger('chatbot')

@csrf_exempt
async def chat_view(request):
    """Async endpoint that processes chat messages using ChatHandler"""
    print("NEWEP-1: Starting chat endpoint function")
    from django.http import JsonResponse
import asyncio

@csrf_exempt
async def chat_view(request):
    """Async endpoint that processes chat messages using ChatHandler"""
    print("NEWEP-1: Starting chat endpoint function")
    try:
        body = await request.read()
        data = json.loads(body)
        user_id = data.get('user_id')
        user_message = data.get('message', '')
        print(f"NEWEP-4: Got user_id={user_id}, message={user_message}")
        
        session_data = await get_session(user_id)
        handler = ChatHandler(session_data, user_message, user_id)
        await handler.initialize()
        
        result = await handler.handle_message()
        print(f"NEWEP-10: handle_message returned: {result}, type={type(result)}")
        
        if isinstance(result, tuple) and len(result) == 2:
            response, updated_session = result
            print(f"NEWEP-12: response={response}, type={type(response)}, updated_session type={type(updated_session)}")
        else:
            response = result
            print(f"NEWEP-13: response={response}, type={type(response)}")
        
        if isinstance(response, dict):
            final_response = JsonResponse(response)
            print("NEWEP-15: Converted dict to JsonResponse")
        elif isinstance(response, JsonResponse):
            final_response = response
            print("NEWEP-16: Using JsonResponse directly")
        else:
            print(f"NEWEP-17: Unexpected response type: {type(response)}")
            logger.error(f"Unexpected response type: {type(response)}")
            final_response = JsonResponse({"messages": ["An unexpected error occurred."]})
        
        print(f"NEWEP-18: Returning final_response, type={type(final_response)}")
        return final_response
        
    except Exception as e:
        print(f"NEWEP-ERROR: Exception: {str(e)}")
        import traceback
        print(f"NEWEP-ERROR-TRACE: {traceback.format_exc()}")
        logger.error(f"Error handling chat request: {str(e)}", exc_info=True)
        return JsonResponse({"messages": ["Sorry, something went wrong."]})