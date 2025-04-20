# chatbot/celery.py (Create this file in your Django project root)

from __future__ import absolute_import, unicode_literals
import os
import logging
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')
logger = logging.getLogger(__name__)
logger.debug("Initializing Celery")
# Create the Celery app
app = Celery('anna_project')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs
app.autodiscover_tasks()

# Define your beat schedule
app.conf.beat_schedule = {
    'send-post-discharge-reminders-hourly': {
        'task': 'chatbot.tasks.send_post_discharge_reminders_task',
        'schedule': crontab(minute=0, hour='*/1'),
    },
    'preventive-care-reminders-daily': {
        'task': 'chatbot.tasks.process_preventive_care_reminders',
        'schedule': crontab(hour=8, minute=0),
    },
    'process-medication-reminders-every-two-hours': {
        'task': 'chatbot.tasks.process_medication_reminders_task',
        'schedule': crontab(minute=0, hour='*/2'),
    },
}

@app.task(bind=True)
def debug_task(self):
    logger.debug(f'Request: {self.request!r}')
logger.debug("Celery initialization complete")