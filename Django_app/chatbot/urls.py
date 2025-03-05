# chatbot/urls.py
from django.urls import path
from .views.api.chat_endpoint import chat_view
from .views.api.test_endpoint import test_view
from .views.api.sync_test import sync_test_view
from .views.api.minimal_chat import minimal_chat
from .views.api.sync_wrapper import sync_chat_view
import asyncio
import inspect

print(f"DEBUG-URLS: Is chat_view async (asyncio)? {asyncio.iscoroutinefunction(chat_view)}")
print(f"DEBUG-URLS: Is chat_view async (inspect)? {inspect.iscoroutinefunction(chat_view)}")
print(f"DEBUG-URLS: chat_view type: {type(chat_view)}")
print(f"DEBUG-URLS: chat_view attributes: {dir(chat_view)}")
print(f"DEBUG-URLS: Is minimal_chat async? {asyncio.iscoroutinefunction(minimal_chat)}")

urlpatterns = [
    # Original async views (currently not working)
    path('chat/', chat_view, name='chat'),
    path('test/', test_view, name='test'),
    path('minimal-chat/', minimal_chat, name='minimal_chat'),
    
    # Working synchronous views
    path('sync-test/', sync_test_view, name='sync_test'),
    
    # New synchronous wrapper around async functionality
    path('sync-chat/', sync_chat_view, name='sync_chat'),
]