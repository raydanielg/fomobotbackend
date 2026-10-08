import logging

from celery import shared_task

logger = logging.getLogger("fomobot.conversations.tasks")


@shared_task
def push_event_to_inbox(event_id: str):
    """Fan an event out to the org's inbox WebSocket group."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from apps.logs.models import Event

    event = Event.objects.filter(pk=event_id).first()
    if event is None:
        return
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            f"org_{event.organization_id}_inbox",
            {
                "type": "inbox_event",
                "payload": {
                    "id": event.id,
                    "type": event.event_type,
                    "created_at": event.created_at.isoformat(),
                    "data": event.payload,
                },
            },
        )
    except Exception:
        logger.exception("inbox_push_failed event=%s", event_id)
