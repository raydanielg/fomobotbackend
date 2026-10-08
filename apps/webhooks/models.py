from django.db import models

from apps.common.models import SoftDeleteModel

SUBSCRIBABLE_EVENTS = [
    "message.received",
    "message.sent",
    "message.delivered",
    "message.read",
    "message.failed",
    "bot.connected",
    "bot.disconnected",
    "bot.qr_required",
    "bot.session_expired",
    "contact.created",
    "contact.updated",
    "conversation.created",
    "conversation.updated",
]


class Webhook(SoftDeleteModel):
    id_prefix = "whk"

    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"
        DISABLED = "disabled"  # auto-disabled after sustained failures

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="webhooks"
    )
    bot = models.ForeignKey(
        "bots.Bot",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="webhooks",
        help_text="Null = receives events for all org bots.",
    )
    name = models.CharField(max_length=120)
    url = models.URLField(max_length=512)
    secret = models.CharField(max_length=96)  # signing secret (server-generated)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    subscribed_events = models.JSONField(default=list)
    consecutive_failures = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self):
        return f"{self.name} → {self.url}"

    def accepts(self, event_type: str, bot_id: str | None) -> bool:
        if self.status != self.Status.ACTIVE:
            return False
        if self.bot_id and bot_id and self.bot_id != bot_id:
            return False
        return "*" in (self.subscribed_events or []) or event_type in (
            self.subscribed_events or []
        )


class WebhookDelivery(models.Model):
    """Immutable delivery attempt log for a webhook + event pair."""

    class Status(models.TextChoices):
        PENDING = "pending"
        DELIVERED = "delivered"
        RETRYING = "retrying"
        FAILED = "failed"

    id = models.CharField(max_length=64, primary_key=True, editable=False)
    webhook = models.ForeignKey(
        Webhook, on_delete=models.CASCADE, related_name="deliveries"
    )
    event = models.ForeignKey(
        "logs.Event", on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempt_count = models.PositiveIntegerField(default=0)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)  # truncated
    error = models.TextField(blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["webhook", "event"], name="uniq_delivery_webhook_event"
            )
        ]
        indexes = [models.Index(fields=["status", "next_retry_at"])]

    def save(self, *args, **kwargs):
        if not self.id:
            from apps.common.utils import new_id

            self.id = new_id("whd")
        super().save(*args, **kwargs)
