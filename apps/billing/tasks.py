import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("fomobot.billing")


@shared_task
def reset_usage_counters():
    """Daily housekeeping: drop usage rows older than 90 days."""
    from apps.billing.models import UsageRecord

    cutoff = timezone.now().date() - timedelta(days=90)
    deleted, _ = UsageRecord.objects.filter(period_start__lt=cutoff).delete()
    logger.info("usage_cleanup deleted=%s", deleted)
