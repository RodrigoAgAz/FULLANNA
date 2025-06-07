"""
Centralized Configuration Management for ANNA
Provides centralized access to all application settings
"""

import os
import logging
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class AppConfig:
    """Centralized configuration management for ANNA"""
    
    # Core Service URLs
    FHIR_SERVER_URL = os.getenv('FHIR_SERVER_URL', getattr(settings, 'FHIR_SERVER_URL', 'http://localhost:8080/fhir'))
    MEDLINEPLUS_API_URL = "https://connect.medlineplus.gov/service"
    MEDLINEPLUS_SEARCH_URL = "https://wsearch.nlm.nih.gov/ws/query"
    
    # API Keys and Credentials
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', getattr(settings, 'OPENAI_API_KEY', ''))
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', getattr(settings, 'TWILIO_ACCOUNT_SID', ''))
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', getattr(settings, 'TWILIO_AUTH_TOKEN', ''))
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', getattr(settings, 'TWILIO_PHONE_NUMBER', ''))
    
    # Redis Configuration
    REDIS_URL = os.getenv('REDIS_URL', getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
    SESSION_TTL_SECONDS = int(os.getenv('SESSION_TTL_SECONDS', getattr(settings, 'SESSION_TTL_SECONDS', 3600)))
    
    # Email Configuration
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@anna-health.com'))
    EMAIL_VERIFICATION_EXPIRY_MINUTES = int(os.getenv('EMAIL_VERIFICATION_EXPIRY_MINUTES', '15'))
    
    # Feature Flags
    ENABLE_MEDICATION_REMINDERS = os.getenv('ENABLE_MEDICATION_REMINDERS', 'true').lower() == 'true'
    ENABLE_POST_DISCHARGE = os.getenv('ENABLE_POST_DISCHARGE', 'true').lower() == 'true'
    ENABLE_AUDIT_LOGGING = os.getenv('ENABLE_AUDIT_LOGGING', 'true').lower() == 'true'
    ENABLE_SMS_NOTIFICATIONS = os.getenv('ENABLE_SMS_NOTIFICATIONS', 'true').lower() == 'true'
    ENABLE_EMAIL_NOTIFICATIONS = os.getenv('ENABLE_EMAIL_NOTIFICATIONS', 'true').lower() == 'true'
    ENABLE_MULTILINGUAL_SUPPORT = os.getenv('ENABLE_MULTILINGUAL_SUPPORT', 'true').lower() == 'true'
    
    # Application Limits and Thresholds
    MAX_CONVERSATION_HISTORY = int(os.getenv('MAX_CONVERSATION_HISTORY', '50'))
    APPOINTMENT_SLOT_DURATION_MINUTES = int(os.getenv('APPOINTMENT_SLOT_DURATION_MINUTES', '30'))
    MAX_DAILY_MESSAGES_PER_USER = int(os.getenv('MAX_DAILY_MESSAGES_PER_USER', '100'))
    MAX_VERIFICATION_ATTEMPTS = int(os.getenv('MAX_VERIFICATION_ATTEMPTS', '3'))
    
    # AI Model Configuration
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    OPENAI_TEMPERATURE = float(os.getenv('OPENAI_TEMPERATURE', '0.3'))
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', '1000'))
    OPENAI_TIMEOUT_SECONDS = int(os.getenv('OPENAI_TIMEOUT_SECONDS', '30'))
    
    # Security Configuration
    REQUIRE_EMAIL_VERIFICATION = os.getenv('REQUIRE_EMAIL_VERIFICATION', 'true').lower() == 'true'
    ENABLE_RATE_LIMITING = os.getenv('ENABLE_RATE_LIMITING', 'true').lower() == 'true'
    MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
    LOCKOUT_DURATION_MINUTES = int(os.getenv('LOCKOUT_DURATION_MINUTES', '15'))
    
    # Audit and Compliance
    AUDIT_LOG_TO_FILE = os.getenv('AUDIT_LOG_TO_FILE', 'true').lower() == 'true'
    AUDIT_LOG_TO_DATABASE = os.getenv('AUDIT_LOG_TO_DATABASE', 'false').lower() == 'true'
    AUDIT_LOG_TO_EXTERNAL = os.getenv('AUDIT_LOG_TO_EXTERNAL', 'false').lower() == 'true'
    AUDIT_SERVICE_URL = os.getenv('AUDIT_SERVICE_URL', '')
    AUDIT_SERVICE_TOKEN = os.getenv('AUDIT_SERVICE_TOKEN', '')
    
    # Timezone and Localization
    DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', 'America/New_York')
    SUPPORTED_LANGUAGES = ['en', 'es']  # English, Spanish
    DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'en')
    
    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT = int(os.getenv('HEALTH_CHECK_TIMEOUT', '10'))
    HEALTH_CHECK_ENABLED = os.getenv('HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
    
    # Cache Configuration
    CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '300'))  # 5 minutes
    ENABLE_RESPONSE_CACHING = os.getenv('ENABLE_RESPONSE_CACHING', 'true').lower() == 'true'
    
    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        config = {}
        for key in dir(cls):
            if not key.startswith('_') and not callable(getattr(cls, key)):
                value = getattr(cls, key)
                # Don't expose sensitive information
                if 'KEY' in key or 'TOKEN' in key or 'PASSWORD' in key:
                    value = '***' if value else ''
                config[key] = value
        return config
    
    @classmethod
    def validate_required_settings(cls) -> bool:
        """Validate required configuration settings"""
        required_settings = [
            ('FHIR_SERVER_URL', cls.FHIR_SERVER_URL),
            ('OPENAI_API_KEY', cls.OPENAI_API_KEY),
        ]
        
        missing = []
        for name, value in required_settings:
            if not value:
                missing.append(name)
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        logger.info("All required configuration settings are present")
        return True
    
    @classmethod
    def validate_optional_settings(cls) -> Dict[str, Any]:
        """Validate optional settings and return warnings"""
        warnings = {}
        
        # Check Twilio configuration
        if not all([cls.TWILIO_ACCOUNT_SID, cls.TWILIO_AUTH_TOKEN, cls.TWILIO_PHONE_NUMBER]):
            warnings['sms'] = "Twilio not configured - SMS notifications disabled"
        
        # Check email configuration
        if not cls.DEFAULT_FROM_EMAIL:
            warnings['email'] = "Email configuration incomplete - email notifications may not work"
        
        # Check Redis configuration
        if 'redis' not in cls.REDIS_URL.lower():
            warnings['redis'] = "Redis URL looks invalid - session management may not work properly"
        
        # Check audit configuration
        if cls.AUDIT_LOG_TO_EXTERNAL and not cls.AUDIT_SERVICE_URL:
            warnings['audit'] = "External audit logging enabled but no service URL configured"
        
        if warnings:
            for component, warning in warnings.items():
                logger.warning(f"Configuration warning for {component}: {warning}")
        
        return warnings
    
    @classmethod
    def get_feature_flags(cls) -> Dict[str, bool]:
        """Get all feature flags"""
        return {
            'medication_reminders': cls.ENABLE_MEDICATION_REMINDERS,
            'post_discharge': cls.ENABLE_POST_DISCHARGE,
            'audit_logging': cls.ENABLE_AUDIT_LOGGING,
            'sms_notifications': cls.ENABLE_SMS_NOTIFICATIONS,
            'email_notifications': cls.ENABLE_EMAIL_NOTIFICATIONS,
            'multilingual_support': cls.ENABLE_MULTILINGUAL_SUPPORT,
            'rate_limiting': cls.ENABLE_RATE_LIMITING,
            'email_verification': cls.REQUIRE_EMAIL_VERIFICATION,
            'response_caching': cls.ENABLE_RESPONSE_CACHING,
            'health_checks': cls.HEALTH_CHECK_ENABLED
        }
    
    @classmethod
    def get_service_config(cls, service_name: str) -> Dict[str, Any]:
        """Get configuration for a specific service"""
        service_configs = {
            'openai': {
                'api_key': cls.OPENAI_API_KEY,
                'model': cls.OPENAI_MODEL,
                'temperature': cls.OPENAI_TEMPERATURE,
                'max_tokens': cls.OPENAI_MAX_TOKENS,
                'timeout': cls.OPENAI_TIMEOUT_SECONDS
            },
            'twilio': {
                'account_sid': cls.TWILIO_ACCOUNT_SID,
                'auth_token': cls.TWILIO_AUTH_TOKEN,
                'phone_number': cls.TWILIO_PHONE_NUMBER,
                'enabled': cls.ENABLE_SMS_NOTIFICATIONS
            },
            'fhir': {
                'server_url': cls.FHIR_SERVER_URL,
                'timeout': cls.HEALTH_CHECK_TIMEOUT
            },
            'redis': {
                'url': cls.REDIS_URL,
                'session_ttl': cls.SESSION_TTL_SECONDS
            },
            'email': {
                'from_email': cls.DEFAULT_FROM_EMAIL,
                'verification_expiry': cls.EMAIL_VERIFICATION_EXPIRY_MINUTES,
                'enabled': cls.ENABLE_EMAIL_NOTIFICATIONS
            },
            'audit': {
                'enabled': cls.ENABLE_AUDIT_LOGGING,
                'log_to_file': cls.AUDIT_LOG_TO_FILE,
                'log_to_database': cls.AUDIT_LOG_TO_DATABASE,
                'log_to_external': cls.AUDIT_LOG_TO_EXTERNAL,
                'service_url': cls.AUDIT_SERVICE_URL
            }
        }
        
        return service_configs.get(service_name, {})

# Validate configuration on import
try:
    AppConfig.validate_required_settings()
    warnings = AppConfig.validate_optional_settings()
    if not warnings:
        logger.info("ANNA configuration validated successfully")
except Exception as e:
    logger.error(f"Configuration validation failed: {e}")
    raise

# Global configuration instance
config = AppConfig()