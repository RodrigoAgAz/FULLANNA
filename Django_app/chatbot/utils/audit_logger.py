"""
Audit Logger for ANNA
Provides comprehensive audit logging for healthcare compliance
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger('audit')

class AuditLogger:
    """Comprehensive audit logging for healthcare compliance"""
    
    def __init__(self):
        self.enabled = getattr(settings, 'ENABLE_AUDIT_LOGGING', True)
        self.log_to_file = getattr(settings, 'AUDIT_LOG_TO_FILE', True)
        self.log_to_database = getattr(settings, 'AUDIT_LOG_TO_DATABASE', False)
        self.log_to_external = getattr(settings, 'AUDIT_LOG_TO_EXTERNAL', False)
    
    async def log_event(
        self,
        event_type: str,
        user_id: str,
        action: str,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log an audit event"""
        if not self.enabled:
            return
        
        try:
            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "user_id": self._sanitize_user_id(user_id),
                "action": action,
                "resource": resource,
                "status": status,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details or {}
            }
            
            # Log to structured logger (file)
            if self.log_to_file:
                logger.info(json.dumps(event))
            
            # Log to database (if configured)
            if self.log_to_database:
                await self._log_to_database(event)
            
            # Send to external audit service (if configured)
            if self.log_to_external:
                await self._send_to_external_service(event)
                
        except Exception as e:
            logger.error(f"Audit logging error: {e}")
    
    def _sanitize_user_id(self, user_id: str) -> str:
        """Sanitize user ID for logging (hash email addresses)"""
        if '@' in user_id:
            # Hash email addresses for privacy
            import hashlib
            return hashlib.sha256(user_id.encode()).hexdigest()[:12]
        return user_id
    
    async def _log_to_database(self, event: Dict[str, Any]) -> None:
        """Log event to database"""
        try:
            # This would integrate with your audit model
            # For now, we'll skip database logging
            pass
        except Exception as e:
            logger.error(f"Database audit logging error: {e}")
    
    async def _send_to_external_service(self, event: Dict[str, Any]) -> None:
        """Send audit event to external service"""
        try:
            audit_service_url = getattr(settings, 'AUDIT_SERVICE_URL', None)
            audit_service_token = getattr(settings, 'AUDIT_SERVICE_TOKEN', None)
            
            if not audit_service_url:
                return
            
            import httpx
            headers = {}
            if audit_service_token:
                headers["Authorization"] = f"Bearer {audit_service_token}"
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    audit_service_url,
                    json=event,
                    headers=headers,
                    timeout=10
                )
        except Exception as e:
            logger.error(f"External audit service error: {e}")
    
    # Convenience methods for common audit events
    async def log_login(self, user_id: str, success: bool = True, ip_address: Optional[str] = None):
        """Log user login attempt"""
        await self.log_event(
            event_type="authentication",
            user_id=user_id,
            action="login",
            status="success" if success else "failure",
            ip_address=ip_address
        )
    
    async def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str = "read"
    ):
        """Log access to sensitive data"""
        await self.log_event(
            event_type="data_access",
            user_id=user_id,
            action=action,
            resource=f"{resource_type}/{resource_id}"
        )
    
    async def log_conversation(
        self,
        user_id: str,
        intent: str,
        success: bool = True,
        details: Optional[Dict] = None
    ):
        """Log conversation interaction"""
        await self.log_event(
            event_type="conversation",
            user_id=user_id,
            action=intent,
            status="success" if success else "failure",
            details=details
        )
    
    async def log_appointment(
        self,
        user_id: str,
        action: str,
        appointment_id: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """Log appointment-related actions"""
        resource = f"appointment/{appointment_id}" if appointment_id else "appointment"
        await self.log_event(
            event_type="appointment",
            user_id=user_id,
            action=action,
            resource=resource,
            details=details
        )
    
    async def log_medical_query(
        self,
        user_id: str,
        query_type: str,
        topic: Optional[str] = None
    ):
        """Log medical information queries"""
        await self.log_event(
            event_type="medical_query",
            user_id=user_id,
            action=query_type,
            resource=f"medical_info/{topic}" if topic else "medical_info"
        )
    
    async def log_error(
        self,
        user_id: str,
        error_type: str,
        error_message: str,
        details: Optional[Dict] = None
    ):
        """Log error events"""
        await self.log_event(
            event_type="error",
            user_id=user_id,
            action=error_type,
            status="error",
            details={
                "error_message": error_message,
                **(details or {})
            }
        )
    
    async def log_security_event(
        self,
        user_id: str,
        security_event: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """Log security-related events"""
        await self.log_event(
            event_type="security",
            user_id=user_id,
            action=security_event,
            ip_address=ip_address,
            details=details
        )

# Global instance
audit_logger = AuditLogger()

# Convenience functions for backward compatibility
async def log_audit_event(event_type: str, user_id: str, action: str, **kwargs):
    """Log a general audit event"""
    await audit_logger.log_event(event_type, user_id, action, **kwargs)

async def log_login(user_id: str, success: bool = True, ip_address: Optional[str] = None):
    """Log user login attempt"""
    await audit_logger.log_login(user_id, success, ip_address)

async def log_data_access(user_id: str, resource_type: str, resource_id: str, action: str = "read"):
    """Log access to sensitive data"""
    await audit_logger.log_data_access(user_id, resource_type, resource_id, action)

async def log_conversation(user_id: str, intent: str, success: bool = True, details: Optional[Dict] = None):
    """Log conversation interaction"""
    await audit_logger.log_conversation(user_id, intent, success, details)

async def log_appointment(user_id: str, action: str, appointment_id: Optional[str] = None, details: Optional[Dict] = None):
    """Log appointment-related actions"""
    await audit_logger.log_appointment(user_id, action, appointment_id, details)

async def log_medical_query(user_id: str, query_type: str, topic: Optional[str] = None):
    """Log medical information queries"""
    await audit_logger.log_medical_query(user_id, query_type, topic)

async def log_error(user_id: str, error_type: str, error_message: str, details: Optional[Dict] = None):
    """Log error events"""
    await audit_logger.log_error(user_id, error_type, error_message, details)

async def log_security_event(user_id: str, security_event: str, ip_address: Optional[str] = None, details: Optional[Dict] = None):
    """Log security-related events"""
    await audit_logger.log_security_event(user_id, security_event, ip_address, details)