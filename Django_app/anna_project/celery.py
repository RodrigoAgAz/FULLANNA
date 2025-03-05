# chatbot/celery.py (Create this file in your Django project root)

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')
print ("3")
# Create the Celery app
app = Celery('anna_project')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs
app.autodiscover_tasks()

# Define your beat schedule
app.conf.beat_schedule = {
    'send-post-discharge-reminders-hourly': {
        'task': 'chatbot.tasks.send_post_discharge_reminders',
        'schedule': crontab(minute=0, hour='*/1'),  # Every hour
    },
    'example-task': {
        'task': 'your_app.tasks.example_task',
        'schedule': 300.0,  # Run every 300 seconds (5 minutes)
    }
}
app.conf.beat_schedule = {
    'send-post-discharge-reminders-hourly': {
        'task': 'chatbot.tasks.send_post_discharge_reminders',
        'schedule': crontab(minute=0, hour='*/1'),
    },
    'example-task': {
        'task': 'your_app.tasks.example_task',
        'schedule': 300.0,
    },
    'preventive-care-reminders-daily': {
        'task': 'chatbot.tasks.process_preventive_care_reminders',
        'schedule': crontab(hour=8, minute=0),  # runs daily at 8 AM
    },
}


app.conf.beat_schedule.update({
    'process-medication-reminders-every-hour': {
         'task': 'chatbot.tasks.process_medication_reminders_task',
         'schedule': crontab(minute=0, hour='*/2'),  # run every 2 hour
    },
    
})

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
print("4")