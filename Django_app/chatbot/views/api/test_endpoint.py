"""
Simple test endpoint to verify ASGI configuration
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import asyncio
import inspect

@csrf_exempt
async def test_view(request):
    """A very simple async endpoint that just returns a fixed response"""
    print("TEST-ENDPOINT-1: Starting test view")
    
    # For debugging async issues
    def is_coroutine(obj):
        return asyncio.iscoroutine(obj) or inspect.iscoroutine(obj)
    
    try:
        # Create the response
        print("TEST-ENDPOINT-2: Creating response")
        response = JsonResponse({"status": "ok", "message": "Test endpoint working correctly"})
        
        # Check if the response is a coroutine
        print(f"TEST-ENDPOINT-3: Response type: {type(response)}")
        print(f"TEST-ENDPOINT-4: Is response a coroutine: {is_coroutine(response)}")
        
        # Return the response directly, not as a coroutine
        print("TEST-ENDPOINT-5: Returning response")
        return response
    except Exception as e:
        print(f"TEST-ENDPOINT-ERROR: Exception {str(e)}")
        import traceback
        print(f"TEST-ENDPOINT-ERROR-TRACE: {traceback.format_exc()}")
        return JsonResponse({"status": "error", "message": str(e)})