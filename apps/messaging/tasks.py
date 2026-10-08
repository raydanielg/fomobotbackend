import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.messaging.models import Message
from apps.messaging.services import MessageService

logger = logging.getLogger("fomobot.messaging.tasks")


def _backoff(attempt: int) -> int:
    return min(2 ** attempt * 5, 300)  # 5s,10s,20s... capped at 5m


@shared_task(bind=True, max_retries=None, acks_late=True, reject_on_worker_lost=True)
def process_outbound_message(self, message_id: str):
    """Worker: send a queued message via the WhatsApp provider."""
    from apps.whatsapp.models import WhatsAppSession
    from apps.whatsapp.providers import get_provider
    from apps.whatsapp.providers.base import ProviderError

    message = (
        Message.objects.select_related("bot", "organization", "contact")
        .filter(pk=message_id)
        .first()
    )
    if message is None or message.status not in (
        Message.Status.QUEUED,
        Message.Status.SENDING,
    ):
        return

    session = WhatsAppSession.objects.filter(bot=message.bot).first()
    if not session or not session.is_connected:
        # Retry briefly — provider may be reconnecting.
        if message.attempt_count < settings.FOMOBOT["MESSAGE_MAX_ATTEMPTS"]:
            message.attempt_count += 1
            message.save(update_fields=["attempt_count", "updated_at"])
            raise self.retry(countdown=_backoff(message.attempt_count))
        MessageService.mark_failed(message, "Bot is not connected.", "BOT_NOT_CONNECTED")
        return

    message.status = Message.Status.SENDING
    message.attempt_count += 1
    message.save(update_fields=["status", "attempt_count", "updated_at"])

    try:
        result = get_provider(session.provider).send_message(
            session,
            to=message.contact.phone_number,
            message_type=message.message_type,
            text=message.text,
            media_url=message.media_url,
            caption=message.caption,
            metadata=message.metadata,
        )
    except ProviderError as exc:
        if exc.retryable and message.attempt_count < settings.FOMOBOT["MESSAGE_MAX_ATTEMPTS"]:
            message.status = Message.Status.QUEUED
            message.save(update_fields=["status", "updated_at"])
            raise self.retry(countdown=_backoff(message.attempt_count), exc=exc)
        MessageService.mark_failed(message, str(exc), exc.code or "WHATSAPP_ERROR")
        return
    except Exception as exc:
        logger.exception("send_unexpected_error msg=%s", message_id)
        if message.attempt_count < settings.FOMOBOT["MESSAGE_MAX_ATTEMPTS"]:
            message.status = Message.Status.QUEUED
            message.save(update_fields=["status", "updated_at"])
            raise self.retry(countdown=_backoff(message.attempt_count), exc=exc)
        MessageService.mark_failed(message, str(exc), "INTERNAL_ERROR")
        return

    message.status = Message.Status.SENT
    message.provider_message_id = result.provider_message_id
    message.sent_at = timezone.now()
    message.save(
        update_fields=["status", "provider_message_id", "sent_at", "updated_at"]
    )
    from apps.logs.services import emit

    emit(
        "message.sent",
        organization=message.organization,
        bot=message.bot,
        payload={
            "message_id": message.id,
            "conversation_id": message.conversation_id,
            "to": message.contact.phone_number,
            "provider_message_id": result.provider_message_id,
        },
    )
