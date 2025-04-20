import logging
from .security import redact_pii
from typing import Any, Dict, Optional

class RedactPIIFilter(logging.Filter):
    """
    Logging filter that redacts personally identifiable information (PII) from log messages.
    Applies the redact_pii function to both the log record's msg and args.
    
    This ensures that sensitive information like phone numbers, SSNs, emails, etc.,
    are properly redacted before being written to any log output.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Apply PII redaction to the log record
        
        Args:
            record: The log record to filter
            
        Returns:
            True to allow the record to be processed, after redacting PII
        """
        # Redact the main message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = redact_pii(record.msg)
        
        # Redact args if they are strings
        if hasattr(record, 'args') and record.args:
            args = list(record.args) if isinstance(record.args, tuple) else record.args
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    args[i] = redact_pii(arg)
            record.args = tuple(args) if isinstance(record.args, tuple) else args
        
        return True