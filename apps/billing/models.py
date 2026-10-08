"""Plan / subscription scaffolding.

The product is currently FREE, but every entitlement decision flows through
``PlanService`` so paid tiers can be switched on without touching core logic.
"""
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class Plan(BaseModel):
    id_prefix = "plan"

    class Code(models.TextChoices):
        FREE = "free"
        PRO = "pro"
        BUSINESS = "business"
        ENTERPRISE = "enterprise"

    code = models.CharField(max_length=16, choices=Code.choices, unique=True)
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    # Centralized, configurable limits — never hard-code these elsewhere.
    limits = models.JSONField(default=dict)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


DEFAULT_PLAN_LIMITS = {
    Plan.Code.FREE: {
        "max_bots": 2,
        "max_members": 3,
        "messages_per_day": 500,
        "api_requests_per_minute": 60,
        "max_webhooks": 3,
        "max_automation_rules": 5,
        "max_contacts": 1000,
        "log_retention_days": 7,
    },
    Plan.Code.PRO: {
        "max_bots": 10,
        "max_members": 15,
        "messages_per_day": 20000,
        "api_requests_per_minute": 300,
        "max_webhooks": 20,
        "max_automation_rules": 50,
        "max_contacts": 50000,
        "log_retention_days": 30,
    },
    Plan.Code.BUSINESS: {
        "max_bots": 50,
        "max_members": 100,
        "messages_per_day": 200000,
        "api_requests_per_minute": 1200,
        "max_webhooks": 100,
        "max_automation_rules": 250,
        "max_contacts": 500000,
        "log_retention_days": 90,
    },
    Plan.Code.ENTERPRISE: {
        "max_bots": 0,  # 0 = unlimited
        "max_members": 0,
        "messages_per_day": 0,
        "api_requests_per_minute": 5000,
        "max_webhooks": 0,
        "max_automation_rules": 0,
        "max_contacts": 0,
        "log_retention_days": 365,
    },
}


class Subscription(BaseModel):
    """Org ↔ plan relationship. Only one ACTIVE subscription per org."""

    id_prefix = "sub"

    class Status(models.TextChoices):
        ACTIVE = "active"
        TRIALING = "trialing"
        PAST_DUE = "past_due"
        CANCELED = "canceled"
        EXPIRED = "expired"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    provider = models.CharField(max_length=32, blank=True)  # e.g. stripe — future
    provider_subscription_id = models.CharField(max_length=128, blank=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "status"])]


class UsageRecord(BaseModel):
    """Metered usage per org per UTC day (messages, api calls, ...)."""

    id_prefix = "usg"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="usage_records"
    )
    metric = models.CharField(max_length=64)
    period_start = models.DateField()
    count = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "metric", "period_start"],
                name="uniq_usage_org_metric_period",
            )
        ]
        indexes = [models.Index(fields=["organization", "metric", "period_start"])]


class Invoice(BaseModel):
    """Placeholder for future payment-provider invoices."""

    id_prefix = "inv"

    class Status(models.TextChoices):
        DRAFT = "draft"
        OPEN = "open"
        PAID = "paid"
        VOID = "void"
        UNCOLLECTIBLE = "uncollectible"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="invoices"
    )
    subscription = models.ForeignKey(
        Subscription, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    provider_invoice_id = models.CharField(max_length=128, blank=True)
