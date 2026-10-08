import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.billing.models import DEFAULT_PLAN_LIMITS, Plan, Subscription, UsageRecord
from apps.common import exceptions

logger = logging.getLogger("fomobot.billing")


class PlanService:
    """Centralized plan/limit resolution — the ONLY place limits are read."""

    DEFAULT_LIMITS_FALLBACK = DEFAULT_PLAN_LIMITS[Plan.Code.FREE]

    @staticmethod
    def get_plan(organization) -> Plan:
        if organization.plan_id and organization.plan:
            return organization.plan
        sub = (
            Subscription.objects.filter(
                organization=organization, status=Subscription.Status.ACTIVE
            )
            .select_related("plan")
            .first()
        )
        if sub:
            return sub.plan
        return PlanService.get_free_plan()

    @staticmethod
    def get_free_plan() -> Plan:
        plan, _ = Plan.objects.get_or_create(
            code=Plan.Code.FREE,
            defaults={
                "name": "Free",
                "limits": DEFAULT_PLAN_LIMITS[Plan.Code.FREE],
            },
        )
        return plan

    @staticmethod
    def get_limit(organization, key: str):
        plan = PlanService.get_plan(organization)
        limits = plan.limits or {}
        return limits.get(key, PlanService.DEFAULT_LIMITS_FALLBACK.get(key))

    @staticmethod
    def check_limit(organization, key: str, current_count: int, noun: str = "resource"):
        """Raise PlanLimitReached if current_count >= configured limit (0=unlimited)."""
        limit = PlanService.get_limit(organization, key)
        if limit and int(limit) > 0 and current_count >= int(limit):
            raise exceptions.PlanLimitReached(
                detail=f"Plan limit reached for {noun} (limit: {limit}). Upgrade your plan."
            )

    @staticmethod
    @transaction.atomic
    def increment_usage(organization, metric: str, amount: int = 1) -> int:
        """Increment today's usage counter; returns the new count."""
        record, _ = UsageRecord.objects.select_for_update().get_or_create(
            organization=organization, metric=metric, period_start=timezone.localdate()
        )
        record.count = F("count") + amount
        record.save(update_fields=["count"])
        record.refresh_from_db(fields=["count"])
        return record.count

    @staticmethod
    def usage_today(organization, metric: str) -> int:
        return (
            UsageRecord.objects.filter(
                organization=organization, metric=metric, period_start=timezone.localdate()
            )
            .values_list("count", flat=True)
            .first()
            or 0
        )
