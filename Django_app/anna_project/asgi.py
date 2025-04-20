# Django_app/anna_project/asgi.py
"""
ASGI config for anna_project.
It exposes the ASGI callable as a module-level variable named 'application'.
"""

import os
import logging
logger = logging.getLogger(__name__)
logger.debug(f"DJANGO_SETTINGS_MODULE at ASGI startup = {os.environ.get('DJANGO_SETTINGS_MODULE')}")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')

# Import Django ASGI application first
from django.core.asgi import get_asgi_application

logger.debug("Loading Django ASGI application")

# Get the Django ASGI application
application = get_asgi_application()

logger.debug("Django ASGI application loaded")

# Import any other routing frameworks if needed
try:
    from channels.routing import ProtocolTypeRouter
    from channels.auth import AuthMiddlewareStack
    
    logger.debug("Setting up protocol router")
    # Set up ProtocolTypeRouter if using channels
    application = ProtocolTypeRouter({
        "http": application,  # Django ASGI application
    })
    logger.debug("Protocol router setup complete")
except ImportError:
    # If channels isn't available, just use the Django ASGI application
    logger.debug("Channels not available, using only Django ASGI application")