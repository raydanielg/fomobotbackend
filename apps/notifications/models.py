from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Notification(BaseModel):
    id_prefix = "ntf"

    class Type(models.TextChoices):
        BOT_CONNECTED = "bot.connected"
        BOT_DISCONNECTED = "bot.disconnected"
        WEBHOOK_FAILED = "webhook.failed"
        API_KEY_CREATED = "api_key.created"
        SECURITY = "security"
        SYSTEM = "system"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="notifications"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="Null = broadcast to org members.",
    )
    type = models.CharField(max_length=32, choices=Type.choices, default=Type.SYSTEM)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]
