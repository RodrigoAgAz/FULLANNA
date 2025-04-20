"""
Explicit test endpoint to diagnose routing issues
"""
from django.http import JsonResponse

import logging
logger = logging.getLogger(__name__)

async def explicit_test(request):
    """A very simple test endpoint that returns a specific response"""
    logger.debug("Explicit test endpoint called")
    return JsonResponse({"message": "This is from the explicit test endpoint"})