# chatbot/urls.py - FIXED
from django.urls import path
from .views.api.endpoints import chat

# IMPORTANT: This file was edited at:
print("URLS FIXED: Using only existing endpoints")

urlpatterns = [
    # Chat endpoint - only include endpoints that exist
    path('chat/', chat, name='chat'),
]