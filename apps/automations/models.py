from django.db import models

from apps.common.models import BaseModel, SoftDeleteModel


class Automation(SoftDeleteModel):
    """WHEN <trigger> IF <conditions> THEN <actions>."""

    id_prefix = "auto"

    class Trigger(models.TextChoices):
        MESSAGE_RECEIVED = "message.received"
        MESSAGE_SENT = "message.sent"
        CONTACT_CREATED = "contact.created"
        CONVERSATION_CREATED = "conversation.created"
        KEYWORD_DETECTED = "keyword.detected"  # future, evaluated via contains condition
        BOT_CONNECTED = "bot.connected"
        BOT_DISCONNECTED = "bot.disconnected"

    class Status(models.TextChoices):
        ACTIVE = "active"
        PAUSED = "paused"
        DRAFT = "draft"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="automations"
    )
    bot = models.ForeignKey(
        "bots.Bot",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="automations",
        help_text="Null = applies to all org bots.",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=64, choices=Trigger.choices, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    priority = models.PositiveIntegerField(default=100)
    run_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["priority", "created_at"]
        indexes = [models.Index(fields=["organization", "trigger_type", "status"])]


class AutomationCondition(BaseModel):
    id_prefix = "cond"

    class Operator(models.TextChoices):
        EQUALS = "equals"
        NOT_EQUALS = "not_equals"
        CONTAINS = "contains"
        NOT_CONTAINS = "not_contains"
        STARTS_WITH = "starts_with"
        EXISTS = "exists"

    automation = models.ForeignKey(
        Automation, on_delete=models.CASCADE, related_name="conditions"
    )
    field = models.CharField(
        max_length=128, help_text="Dotted path into the event payload, e.g. 'text'"
    )
    operator = models.CharField(max_length=16, choices=Operator.choices)
    value = models.CharField(max_length=512, blank=True)
    case_insensitive = models.BooleanField(default=True)


class AutomationAction(BaseModel):
    id_prefix = "act"

    class Type(models.TextChoices):
        SEND_MESSAGE = "send_message"
        SEND_TEMPLATE = "send_template"
        ADD_TAG = "add_tag"
        REMOVE_TAG = "remove_tag"
        ASSIGN_CONVERSATION = "assign_conversation"
        CALL_WEBHOOK = "call_webhook"
        DELAY = "delay"

    automation = models.ForeignKey(
        Automation, on_delete=models.CASCADE, related_name="actions"
    )
    action_type = models.CharField(max_length=32, choices=Type.choices)
    config = models.JSONField(default=dict)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class AutomationRun(BaseModel):
    """Execution log for automation runs."""

    id_prefix = "run"

    class Status(models.TextChoices):
        SUCCESS = "success"
        PARTIAL = "partial"
        FAILED = "failed"
        SKIPPED = "skipped"

    automation = models.ForeignKey(
        Automation, on_delete=models.CASCADE, related_name="runs"
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    event = models.ForeignKey(
        "logs.Event", null=True, blank=True, on_delete=models.SET_NULL
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    log = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["automation", "created_at"])]
