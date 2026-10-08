from django.db import models
from django.utils.text import slugify

from apps.common.models import SoftDeleteModel


class Bot(SoftDeleteModel):
    """A Bot represents one WhatsApp connection owned by an organization."""

    id_prefix = "bot"

    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"
        DISABLED = "disabled"
        DELETED = "deleted"

    class ConnectionStatus(models.TextChoices):
        DISCONNECTED = "disconnected"
        CONNECTING = "connecting"
        QR_REQUIRED = "qr_required"
        CONNECTED = "connected"
        RECONNECTING = "reconnecting"
        LOGGED_OUT = "logged_out"
        ERROR = "error"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="bots"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    description = models.TextField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True, db_index=True)
    phone_country = models.CharField(max_length=2, blank=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    connection_status = models.CharField(
        max_length=16,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.DISCONNECTED,
        db_index=True,
    )

    last_connected_at = models.DateTimeField(null=True, blank=True)
    last_disconnected_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    settings = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="uniq_bot_org_slug"
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["connection_status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.organization_id})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "bot"
        super().save(*args, **kwargs)
