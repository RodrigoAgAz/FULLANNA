"""
Simple synchronous test endpoint
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def sync_test_view(request):
    """A synchronous view that just returns a fixed response"""
    print("SYNC-TEST: This is the synchronous test view")
    return JsonResponse({"status": "ok", "message": "Synchronous test endpoint working correctly"})