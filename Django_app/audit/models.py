import uuid
from django.db import models

class AuditEntry(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor       = models.CharField(max_length=50)      # user_id / system
    action      = models.CharField(max_length=120)
    resource    = models.CharField(max_length=120)
    metadata    = models.JSONField()
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["actor", "resource"])]
        get_latest_by = "created_at"