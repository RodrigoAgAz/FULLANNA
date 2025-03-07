from django.http import JsonResponse
import json
import logging
import inspect
from asgiref.sync import sync_to_async
from inspect import iscoroutinefunction

from chatbot.views.services.session import get_session
from chatbot.views.handlers.chat_handler import ChatHandler

logger = logging.getLogger('chatbot')


async def chat(request):
    """Async endpoint that processes chat messages using ChatHandler"""
    print("DEBUG-EP-1: Starting chat endpoint function")
    print(f"DEBUG-EP-REQUEST: URL={request.path}, METHOD={request.method}")
    
    # Debug logging to confirm we're hitting this function
    if request.path == "/chatbot/chat/":
        print("DEBUG-EP-CONTINUING: Passing request to chat handler")
    
    try:
        logger.debug("chat function called")
        print("DEBUG-EP-2: About to read request body")
        body = request.body  # This is bytes
        print("DEBUG-EP-3: Parsed request body")
        data = json.loads(body.decode('utf-8'))  # Decode to string and parse JSON
        user_id = data.get('user_id')
        user_message = data.get('message', '')
        print(f"DEBUG-EP-4: Got user_id={user_id}, message={user_message}")

        print("DEBUG-EP-5: Getting session data")
        session_data = await get_session(user_id)
        print(f"Is ChatHandler.__init__ a coroutine function? {iscoroutinefunction(ChatHandler.__init__)}")
        print("DEBUG-EP-6: Creating ChatHandler")
        handler = ChatHandler(session_data, user_message, user_id)
        print("DEBUG-EP-7: About to initialize handler")
        await handler.initialize()  # Initialize handler
        print("DEBUG-EP-8: Handler initialized")
        
        print("DEBUG-EP-9: About to call handle_message")
        result = await handler.handle_message()  # This needs to be awaited
        print(f"DEBUG-EP-10: handle_message returned, type={type(result)}, is coroutine={inspect.iscoroutine(result)}")
        
        print("DEBUG-EP-11: Processing result")
        # Check if result is a tuple (response, session) or just response
        if isinstance(result, tuple) and len(result) == 2:
            print("DEBUG-EP-12: Result is a tuple")
            response, updated_session = result
        else:
            print("DEBUG-EP-13: Result is not a tuple")
            response = result
            updated_session = session_data
        
        # Ensure we return a JsonResponse object
        print(f"DEBUG-EP-14: Response type is {type(response)}")
        if isinstance(response, dict):
            print("DEBUG-EP-15: Converting dict to JsonResponse")
            final_response = JsonResponse(response)
        elif isinstance(response, JsonResponse):
            print("DEBUG-EP-16: Using JsonResponse directly")
            final_response = response
        else:
            print(f"DEBUG-EP-17: Unexpected response type: {type(response)}")
            logger.error(f"Unexpected response type: {type(response)}")
            final_response = JsonResponse({"messages": ["An unexpected error occurred."]})
            
        print("DEBUG-EP-18: About to return final response")
        print(f"DEBUG-EP-19: Final response type: {type(final_response)}, is coroutine={inspect.iscoroutine(final_response)}")
        return final_response
            
    except Exception as e:
        print(f"DEBUG-EP-ERROR: Exception in chat endpoint: {str(e)}")
        print(f"DEBUG-EP-ERROR-TYPE: Exception type: {type(e)}")
        import traceback
        print(f"DEBUG-EP-ERROR-TRACE: {traceback.format_exc()}")
        logger.error(f"Error handling chat request: {str(e)}", exc_info=True)
        return JsonResponse({"messages": ["Sorry, something went wrong."]})