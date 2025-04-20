from django.http import JsonResponse
import json
import logging
from asgiref.sync import sync_to_async
import inspect  # Using this for iscoroutine and other functions

from chatbot.views.services.session import get_session
from chatbot.views.handlers.chat_handler import ChatHandler

logger = logging.getLogger('chatbot')


async def chat(request):
    """Async endpoint that processes chat messages using ChatHandler"""
    logger.debug("Starting chat endpoint function")
    logger.debug(f"Request: URL={request.path}, METHOD={request.method}")
    
    # Debug logging to confirm we're hitting this function
    if request.path == "/chatbot/chat/":
        logger.debug("Passing request to chat handler")
    
    try:
        logger.debug("chat function called")
        logger.debug("About to read request body")
        body = request.body  # This is bytes
        logger.debug("Parsed request body")
        data = json.loads(body.decode('utf-8'))  # Decode to string and parse JSON
        user_id = data.get('user_id')
        user_message = data.get('message', '')
        logger.debug(f"Got user_id={user_id}, message={user_message}")

        logger.debug("Getting session data")
        session_data = await get_session(user_id)
        logger.debug(f"Is ChatHandler.__init__ a coroutine function? {inspect.iscoroutinefunction(ChatHandler.__init__)}")
        logger.debug("Creating ChatHandler")
        handler = ChatHandler(session_data, user_message, user_id)
        logger.debug("About to initialize handler")
        await handler.initialize()  # Initialize handler
        logger.debug("Handler initialized")
        
        logger.debug("About to call handle_message")
        result = await handler.handle_message()  # This needs to be awaited
        logger.debug(f"handle_message returned, type={type(result)}, is coroutine={inspect.iscoroutine(result)}")
        
        logger.debug("Processing result")
        # Check if result is a tuple (response, session) or just response
        if isinstance(result, tuple) and len(result) == 2:
            logger.debug("Result is a tuple")
            response, updated_session = result
        else:
            logger.debug("Result is not a tuple")
            response = result
            updated_session = session_data
        
        # Ensure we return a JsonResponse object
        logger.debug(f"Response type is {type(response)}")
        if isinstance(response, dict):
            logger.debug("Converting dict to JsonResponse")
            final_response = JsonResponse(response)
        elif isinstance(response, JsonResponse):
            logger.debug("Using JsonResponse directly")
            final_response = response
        else:
            logger.debug(f"Unexpected response type: {type(response)}")
            logger.error(f"Unexpected response type: {type(response)}")
            final_response = JsonResponse({"messages": ["An unexpected error occurred."]})
            
        logger.debug("About to return final response")
        logger.debug(f"Final response type: {type(final_response)}, is coroutine={inspect.iscoroutine(final_response)}")
        return final_response
            
    except Exception as e:
        logger.error(f"Exception in chat endpoint: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        logger.error(f"Error handling chat request: {str(e)}", exc_info=True)
        return JsonResponse({"messages": ["Sorry, something went wrong."]})