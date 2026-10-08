import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("fomobot.logs")


@shared_task
def enforce_log_retention():
    """Delete API request logs and events past each org's retention window."""
    from apps.billing.services import PlanService
    from apps.logs.models import ApiRequestLog, Event
    from apps.organizations.models import Organization

    total_logs = total_events = 0
    for org in Organization.all_objects.only("id").iterator():
        days = PlanService.get_limit(org, "log_retention_days") or 7
        cutoff = timezone.now() - timedelta(days=int(days))
        total_logs += ApiRequestLog.objects.filter(
            organization=org, created_at__lt=cutoff
        ).delete()[0]
        total_events += Event.objects.filter(
            organization=org, created_at__lt=cutoff
        ).delete()[0]
    logger.info("log_retention deleted_logs=%s deleted_events=%s", total_logs, total_events)
