import logging
import inspect
import types
import sys
import traceback
from functools import wraps

# Configure logging
debug_logger = logging.getLogger('chatbot.debug')
debug_logger.setLevel(logging.DEBUG)

# Create file handler
file_handler = logging.FileHandler('chat_handler_debug.log')
file_handler.setLevel(logging.DEBUG)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
debug_logger.addHandler(file_handler)
debug_logger.addHandler(console_handler)

def trace_async_calls(cls):
    """
    Class decorator to trace all async method calls in ChatHandler
    """
    original_methods = {}
    
    # Store original methods and wrap them with debug logging
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if inspect.iscoroutinefunction(method):
            original_methods[name] = method
            
            @wraps(method)
            async def wrapped_method(self, *args, **kwargs):
                caller_frame = sys._getframe(1)
                caller_info = f"{caller_frame.f_code.co_filename}:{caller_frame.f_lineno}"
                
                debug_logger.debug(f"ENTER async {cls.__name__}.{method.__name__} called from {caller_info}")
                debug_logger.debug(f"  args: {args}")
                debug_logger.debug(f"  kwargs: {kwargs}")
                
                try:
                    result = await method(self, *args, **kwargs)
                    result_type = type(result).__name__
                    is_coroutine = inspect.iscoroutine(result)
                    debug_logger.debug(f"EXIT  async {cls.__name__}.{method.__name__} returned {result_type} (is_coroutine={is_coroutine})")
                    
                    if isinstance(result, tuple):
                        debug_logger.debug(f"  result is a tuple with len={len(result)}")
                        for i, item in enumerate(result):
                            debug_logger.debug(f"  result[{i}] type: {type(item).__name__}")
                    
                    return result
                except Exception as e:
                    debug_logger.error(f"ERROR in async {cls.__name__}.{method.__name__}: {str(e)}")
                    debug_logger.error(traceback.format_exc())
                    raise
            
            setattr(cls, name, wrapped_method)
    
    # Also wrap normal methods to detect if they're calling async methods without await
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if name not in original_methods and not inspect.iscoroutinefunction(method):
            original_methods[name] = method
            
            @wraps(method)
            def wrapped_normal_method(self, *args, **kwargs):
                debug_logger.debug(f"ENTER sync {cls.__name__}.{method.__name__}")
                
                try:
                    result = method(self, *args, **kwargs)
                    result_type = type(result).__name__
                    is_coroutine = inspect.iscoroutine(result)
                    debug_logger.debug(f"EXIT  sync {cls.__name__}.{method.__name__} returned {result_type} (is_coroutine={is_coroutine})")
                    
                    if is_coroutine:
                        debug_logger.error(f"WARNING: {cls.__name__}.{method.__name__} returned a coroutine without await!")
                    
                    return result
                except Exception as e:
                    debug_logger.error(f"ERROR in sync {cls.__name__}.{method.__name__}: {str(e)}")
                    debug_logger.error(traceback.format_exc())
                    raise
            
            setattr(cls, name, wrapped_normal_method)
    
    # Store original methods for reference
    cls._original_methods = original_methods
    return cls

def debug_intent_handlers(cls_instance):
    """
    Debug function to inspect all intent handlers in a ChatHandler instance.
    Call this after initialization to check all registered handlers.
    """
    debug_logger.debug("--- Inspecting Intent Handlers ---")
    for intent, handler in cls_instance.intent_handlers.items():
        is_async = inspect.iscoroutinefunction(handler)
        debug_logger.debug(f"Intent: {intent}, Handler: {handler.__name__}, Is Async: {is_async}")
    debug_logger.debug("--- End Intent Handlers Inspection ---")

async def trace_handler_execution(handler, *args, **kwargs):
    """
    Utility to trace a specific handler execution.
    Helps test individual handlers without running the full flow.
    """
    debug_logger.debug(f"Testing handler: {handler.__name__}")
    debug_logger.debug(f"Args: {args}")
    debug_logger.debug(f"Kwargs: {kwargs}")
    
    try:
        if inspect.iscoroutinefunction(handler):
            debug_logger.debug(f"{handler.__name__} is an async function, awaiting it")
            result = await handler(*args, **kwargs)
        else:
            debug_logger.debug(f"{handler.__name__} is a regular function, calling it directly")
            result = handler(*args, **kwargs)
        
        debug_logger.debug(f"Handler result type: {type(result).__name__}")
        if inspect.iscoroutine(result):
            debug_logger.error(f"WARNING: {handler.__name__} returned a coroutine that wasn't awaited!")
            # Try to handle it properly
            result = await result
            debug_logger.debug(f"After awaiting, result type: {type(result).__name__}")
            
        return result
    except Exception as e:
        debug_logger.error(f"Error in handler execution: {str(e)}")
        debug_logger.error(traceback.format_exc())
        raise

