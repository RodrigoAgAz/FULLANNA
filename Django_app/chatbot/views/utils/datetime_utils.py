from datetime import datetime, timedelta
from chatbot.views.config import config as app_config
from zoneinfo import ZoneInfo
import re
import dateparser
from datetime import datetime, timedelta, time
import logging
from django.conf import settings
import openai
openai.api_key = settings.OPENAI_API_KEY
# Configure logging
logger = logging.getLogger('chatbot')

from chatbot.views.config import config as app_config

fhir_client = app_config.fhir_client

# Initialize OpenAI client
client = settings.OPENAI_API_KEY


def parse_datetime(text):
    """
    Parse date and time from natural language text.
    Returns tuple of (datetime object, confidence level)
    """
    try:
        # Clean the text
        text = text.lower().strip()
        
        # Get current time in UTC
        now = datetime.now(ZoneInfo("UTC"))
        
        # Handle "tomorrow" explicitly
        if "tomorrow" in text:
            # Start with tomorrow's date
            target_date = now.date() + timedelta(days=1)
            
            # Extract time
            time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                if time_match.group(3) == 'pm' and hour != 12:
                    hour += 12
                elif time_match.group(3) == 'am' and hour == 12:
                    hour = 0
                
                # Create datetime with extracted time
                parsed = datetime.combine(
                    target_date, 
                    time(hour=hour, minute=minute), 
                    tzinfo=ZoneInfo("UTC")
                )
                return parsed, 'high'
        
        # For other cases, use dateparser
        parsed = dateparser.parse(text, settings={
            'PREFER_DATES_FROM': 'future',
            'RELATIVE_BASE': now
        })
        
        if parsed:
            # Make timezone-aware if it isn't already
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
            
            # If only date is mentioned (no time), set a default time
            if any(word in text for word in ['am', 'pm', ':']) or 'time' in text:
                return parsed, 'high'
            else:
                # Set default time to 9:00 AM
                parsed = parsed.replace(hour=9, minute=0, second=0, microsecond=0)
                return parsed, 'medium'
                
        return None, 'low'
        
    except Exception as e:
        logger.error(f"Error parsing datetime: {e}")
        return None, 'low'

def get_current_time(timezone='America/New_York'):
    """
    Get the current time in the specified timezone
    """
    try:
        current_time = datetime.now(ZoneInfo(timezone))
        logger.debug(f"Current time in {timezone}: {current_time}")
        return current_time
    except Exception as e:
        logger.error(f"Error getting current time: {e}")
        # Fallback to UTC if there's an error
        fallback_time = datetime.now(timezone.utc)
        logger.warning(f"Falling back to UTC time: {fallback_time}")
        return fallback_time


def format_datetime(datetime_str):
    """
    Converts a datetime string to a more readable format.
    """
    try:
        parsed_datetime = datetime.fromisoformat(datetime_str.rstrip('Z'))
        return parsed_datetime.strftime("%B %d, %Y at %I:%M %p")
    except Exception as e:
        logger.error(f"Error formatting datetime: {e}")
        return datetime_str


def format_datetime_for_user(dt, timezone='America/New_York'):
    """
    Formats a datetime object into a user-friendly string with validation
    """
    if not dt:
        return None
    
    try:
        # Convert to specified timezone
        local_dt = dt.astimezone(ZoneInfo(timezone))
        
        # Format date and time
        date_str = local_dt.strftime("%A, %B %d, %Y")
        time_str = local_dt.strftime("%I:%M %p").lstrip("0")
        
        return f"{date_str} at {time_str}"
    except Exception as e:
        logger.error(f"Error formatting datetime: {e}")
        return None

def format_slot_time(slot):
    """
    Formats a slot's time for display.
    """
    try:
        start_time = datetime.fromisoformat(slot['start'].replace('Z', '+00:00'))
        return start_time.strftime("%B %d, %Y at %I:%M %p")
    except Exception as e:
        logger.error(f"Error formatting slot time: {e}")
        return "Time not available"
