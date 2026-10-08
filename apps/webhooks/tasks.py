import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("fomobot.webhooks.tasks")


@shared_task
def dispatch_event_to_webhooks(event_id: str):
    from apps.logs.models import Event
    from apps.webhooks.services import WebhookService

    event = Event.objects.filter(pk=event_id).select_related("organization").first()
    if event:
        WebhookService.dispatch(event)


@shared_task(bind=True, max_retries=None, acks_late=True, reject_on_worker_lost=True)
def deliver_webhook(self, delivery_id: str):
    from apps.webhooks.models import WebhookDelivery
    from apps.webhooks.services import WebhookService

    delivery = (
        WebhookDelivery.objects.filter(pk=delivery_id)
        .select_related("webhook", "event", "webhook__organization")
        .first()
    )
    if delivery is None or delivery.status == WebhookDelivery.Status.DELIVERED:
        return
    if delivery.webhook.status != delivery.webhook.Status.ACTIVE:
        return
    try:
        WebhookService.perform_delivery(delivery)
    except Exception as exc:
        logger.exception("deliver_webhook_failed id=%s", delivery_id)
        raise self.retry(countdown=60, exc=exc)


@shared_task
def process_webhook_retries():
    """Beat task: re-queue deliveries whose backoff window elapsed."""
    from apps.webhooks.models import WebhookDelivery

    due = WebhookDelivery.objects.filter(
        status=WebhookDelivery.Status.RETRYING,
        next_retry_at__lte=timezone.now(),
    ).values_list("id", flat=True)[:500]
    for delivery_id in due:
        deliver_webhook.delay(delivery_id)
