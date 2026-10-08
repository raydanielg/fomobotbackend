from django.db import models

from apps.common.models import BaseModel


class Event(BaseModel):
    """Normalized internal event — the unit webhooks/automations subscribe to."""

    id_prefix = "evt"

    class ProcessingStatus(models.TextChoices):
        PENDING = "pending"
        PROCESSING = "processing"
        DELIVERED = "delivered"
        FAILED = "failed"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="events"
    )
    bot = models.ForeignKey(
        "bots.Bot", null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict)
    processing_status = models.CharField(
        max_length=16, choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING, db_index=True,
    )
    retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "event_type", "created_at"]),
        ]


class ApiRequestLog(BaseModel):
    """Audit trail for every developer API request.

    Never stores request bodies, secrets, tokens, or message content.
    """

    id_prefix = "req"

    request_id = models.CharField(max_length=64, unique=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="api_logs",
    )
    api_key = models.ForeignKey(
        "api_keys.APIKey", null=True, blank=True, on_delete=models.SET_NULL
    )
    endpoint = models.CharField(max_length=256)
    method = models.CharField(max_length=8)
    status_code = models.PositiveIntegerField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    response_ms = models.FloatField(default=0)
    error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["api_key", "created_at"]),
        ]
