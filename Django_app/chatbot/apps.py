from django.apps import AppConfig

class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'

    # Comment out the ready method temporarily to test
    # def ready(self):
    #     try:
    #         from chatbot.views.config import config
    #         config.initialize()
    #     except Exception as e:
    #         import logging
    #         logging.error(f"Error initializing chatbot config: {e}")