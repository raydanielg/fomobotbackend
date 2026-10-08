from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Conversation(BaseModel):
    id_prefix = "cnv"

    class Status(models.TextChoices):
        OPEN = "open"
        CLOSED = "closed"
        ARCHIVED = "archived"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="conversations"
    )
    bot = models.ForeignKey(
        "bots.Bot", on_delete=models.CASCADE, related_name="conversations"
    )
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.CASCADE, related_name="conversations"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    last_message = models.ForeignKey(
        "messaging.Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    unread_count = models.PositiveIntegerField(default=0)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_conversations",
    )
    labels = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-last_message_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["bot", "contact"], name="uniq_conversation_bot_contact"
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "-last_message_at"]),
            models.Index(fields=["assigned_user", "status"]),
        ]

    def __str__(self):
        return f"{self.contact} via {self.bot}"
