from django.db import models

from apps.common.models import BaseModel


class Message(BaseModel):
    id_prefix = "msg"

    class Direction(models.TextChoices):
        INBOUND = "inbound"
        OUTBOUND = "outbound"

    class Type(models.TextChoices):
        TEXT = "text"
        IMAGE = "image"
        VIDEO = "video"
        AUDIO = "audio"
        DOCUMENT = "document"
        STICKER = "sticker"
        LOCATION = "location"
        CONTACT = "contact"
        INTERACTIVE = "interactive"

    class Status(models.TextChoices):
        QUEUED = "queued"
        SENDING = "sending"
        SENT = "sent"
        DELIVERED = "delivered"
        READ = "read"
        FAILED = "failed"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="messages"
    )
    bot = models.ForeignKey(
        "bots.Bot", on_delete=models.CASCADE, related_name="messages"
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.CASCADE, related_name="messages"
    )

    direction = models.CharField(max_length=8, choices=Direction.choices, db_index=True)
    message_type = models.CharField(
        max_length=16, choices=Type.choices, default=Type.TEXT
    )
    provider_message_id = models.CharField(max_length=160, blank=True, db_index=True)

    text = models.TextField(blank=True)
    media_url = models.URLField(blank=True)
    media_type = models.CharField(max_length=64, blank=True)
    caption = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=0)

    idempotency_key = models.CharField(max_length=128, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_message_org_idempotency",
            )
        ]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "direction", "created_at"]),
            models.Index(fields=["bot", "provider_message_id"]),
        ]

    def __str__(self):
        return f"{self.direction}:{self.message_type}:{self.id}"
