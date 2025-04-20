from audit.models import AuditEntry

def log_event(actor, action, resource, meta=None):
    """
    Log an auditable event to the database with immutable metadata
    
    Args:
        actor: The user ID or system name that performed the action
        action: The action performed (e.g., "appointment.booked")
        resource: The resource affected (e.g., "appointment/12345")
        meta: Additional JSON-serializable metadata about the event
        
    Returns:
        The created AuditEntry instance
    """
    return AuditEntry.objects.create(
        actor=actor,
        action=action,
        resource=resource,
        metadata=meta or {}
    )