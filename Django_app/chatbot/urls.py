# chatbot/urls.py - FIXED
from django.urls import path
from .views.api.endpoints import chat
from .views.api.test_explicit import explicit_test

# IMPORTANT: This file was edited at:
import logging
logger = logging.getLogger(__name__)
logger.debug("URLS configured with chat and explicit_test endpoints")

urlpatterns = [
    # Chat endpoint - only include endpoints that exist
    path('chat/', chat, name='chat'),
    path('test-explicit/', explicit_test, name='explicit_test'),
]