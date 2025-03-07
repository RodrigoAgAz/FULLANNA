"""
Explicit test endpoint to diagnose routing issues
"""
from django.http import JsonResponse

async def explicit_test(request):
    """A very simple test endpoint that returns a specific response"""
    print("EXPLICIT-TEST: This function was called!")
    return JsonResponse({"message": "This is from the explicit test endpoint"})