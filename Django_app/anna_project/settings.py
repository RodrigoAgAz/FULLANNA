# anna_project/settings.py

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from celery.schedules import crontab
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
# Load environment variables
load_dotenv()

# Set the base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']  # Adjust as needed for production
logger = logging.getLogger(__name__)
logger.debug("Loading Django settings")
INSTALLED_APPS = [
    'django_prometheus',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',       # Added
    'django.contrib.staticfiles',
    'django.contrib.messages',
    'rest_framework',
    'chatbot',
    'audit',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'chatbot.middleware.twilio_signature.TwilioSignatureMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'chatbot.middleware.CustomCsrfMiddleware',  # Replace the default CSRF middleware
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'anna_project.urls'  # Ensure this line is present

# Add ASGI application path
ASGI_APPLICATION = 'anna_project.asgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # Add template directories if needed
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'anna_project.wsgi.application'

# Database
# Using SQLite for simplicity. Configure as needed.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Redis configuration
# Use localhost for local development, 'redis' service name for Docker/containerized environments
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
# Parse REDIS_URL for backwards compatibility
REDIS_HOST = os.getenv('REDIS_HOST', REDIS_URL.split('@')[-1].split(':')[0] if '@' in REDIS_URL else REDIS_URL.split('//')[1].split(':')[0])
REDIS_PORT = int(os.getenv('REDIS_PORT', REDIS_URL.split(':')[-1].split('/')[0]))
REDIS_DB = int(os.getenv('REDIS_DB', REDIS_URL.split('/')[-1]))

# Session timeout in seconds
SESSION_TTL_SECONDS = int(os.getenv('SESSION_TTL_SECONDS', 1800))

# OpenAI API Key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# FHIR Server URL
FHIR_SERVER_URL = os.getenv('FHIR_SERVER_URL', 'http://localhost:8080/fhir/')
FHIR_VERIFY_SSL = os.getenv("FHIR_VERIFY_SSL", "false").lower() == "true"
# Timeout for FHIR requests (seconds)
FHIR_SERVER_TIMEOUT = int(os.getenv('FHIR_SERVER_TIMEOUT', 10))

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    # Add more validators as needed
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'  # Adjust as needed
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'redact_pii': {
            '()': 'chatbot.utils.log_filters.RedactPIIFilter',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'app.log'),
            'formatter': 'verbose',
            'filters': ['redact_pii'],
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['redact_pii'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
            'filters': ['redact_pii'],
        },
        'chatbot': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
            'filters': ['redact_pii'],
        },
        'audit': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
            'filters': ['redact_pii'],
        },
    },
}


# Twilio Settings
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID') 
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER') 

# Sentry Configuration
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
    )


CELERY_BROKER_URL = os.getenv('REDIS_URL', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

# Removed in favor of consolidated schedule in celery.py

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_CONTENT_NEGOTIATION_CLASS': 'rest_framework.negotiation.DefaultContentNegotiation',
}

# CSRF settings
CSRF_COOKIE_NAME = "csrftoken"
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000']  # Add your domains




logger.debug("Finished loading Django settings")