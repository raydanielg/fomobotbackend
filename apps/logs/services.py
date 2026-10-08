import logging

from apps.common.utils import new_event_id
from apps.logs.models import Event

logger = logging.getLogger("fomobot.events")


def emit(event_type: str, *, organization, bot=None, payload: dict | None = None) -> Event:
    """Create a normalized event and fan it out asynchronously.

    Fan-out (webhooks + automations + inbox push) happens in Celery so event
    producers never block on downstream work.
    """
    event = Event.objects.create(
        id=new_event_id(),
        organization=organization,
        bot=bot,
        event_type=event_type,
        payload=payload or {},
    )
    from apps.automations.tasks import dispatch_event_to_automations
    from apps.conversations.tasks import push_event_to_inbox
    from apps.webhooks.tasks import dispatch_event_to_webhooks

    for task in (dispatch_event_to_webhooks, dispatch_event_to_automations, push_event_to_inbox):
        try:
            task.delay(event.id)
        except Exception:
            logger.exception("event_fanout_failed", extra={"event_id": event.id})
    return event
