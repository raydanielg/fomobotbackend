import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("fomobot.whatsapp.tasks")


@shared_task(bind=True, max_retries=3)
def session_health_check(self):
    """Beat task: heartbeat every connected/reconnecting session."""
    from apps.whatsapp.models import WhatsAppSession
    from apps.whatsapp.providers import get_provider
    from apps.whatsapp.providers.base import ProviderError

    sessions = WhatsAppSession.objects.filter(
        state__in=[
            WhatsAppSession.State.CONNECTED,
            WhatsAppSession.State.AUTHENTICATED,
            WhatsAppSession.State.RECONNECTING,
        ]
    ).select_related("bot", "organization")
    for session in sessions.iterator():
        try:
            provider = get_provider(session.provider)
            status = provider.heartbeat(session)
            session.last_heartbeat_at = timezone.now()
            session.save(update_fields=["last_heartbeat_at", "updated_at"])
            if status.state == "disconnected" and session.state == WhatsAppSession.State.CONNECTED:
                reconnect_session.delay(session.bot_id)
        except ProviderError as exc:
            session.last_error = str(exc)
            session.save(update_fields=["last_error", "updated_at"])
            logger.warning("heartbeat_failed session=%s: %s", session.id, exc)


@shared_task
def reconnect_session(bot_id: str):
    from apps.bots.models import Bot
    from apps.whatsapp.services import WhatsAppSessionManager

    bot = Bot.all_objects.filter(pk=bot_id).select_related("organization").first()
    if not bot:
        return
    try:
        WhatsAppSessionManager.reconnect(bot)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reconnect_failed bot=%s: %s", bot_id, exc)


@shared_task
def cleanup_expired_qr():
    """Clear stale QR payloads + expire QR_REQUIRED sessions past timeout."""
    from apps.bots.models import Bot
    from apps.whatsapp.models import WhatsAppSession

    now = timezone.now()
    WhatsAppSession.objects.filter(qr_expires_at__lt=now).update(
        qr_code="", qr_expires_at=None
    )
    timeout = settings.FOMOBOT["SESSION_CONNECT_TIMEOUT_SECONDS"]
    stale = WhatsAppSession.objects.filter(
        state=WhatsAppSession.State.QR_REQUIRED,
        qr_generated_at__lt=now - timezone.timedelta(seconds=timeout),
    ).select_related("bot")
    for session in stale:
        session.state = WhatsAppSession.State.DISCONNECTED
        session.save(update_fields=["state", "updated_at"])
        session.bot.connection_status = Bot.ConnectionStatus.DISCONNECTED
        session.bot.save(update_fields=["connection_status", "updated_at"])


@shared_task
def restore_sessions_on_boot():
    """Restore persisted sessions after a server/worker restart."""
    from apps.whatsapp.models import WhatsAppSession
    from apps.whatsapp.services import WhatsAppSessionManager

    sessions = WhatsAppSession.objects.filter(
        state__in=[
            WhatsAppSession.State.CONNECTED,
            WhatsAppSession.State.AUTHENTICATED,
            WhatsAppSession.State.RECONNECTING,
        ]
    ).exclude(credentials_encrypted="").select_related("bot")
    for session in sessions.iterator():
        try:
            WhatsAppSessionManager.reconnect(session.bot)
        except Exception as exc:  # noqa: BLE001
            logger.warning("restore_failed session=%s: %s", session.id, exc)


@shared_task
def provider_webhook_dispatch(provider: str, event: dict):
    """Entry point for provider webhook/poll events — dedupes, then handles."""
    from django.db import IntegrityError

    from apps.common.utils import new_id
    from apps.whatsapp.models import ProviderEvent

    provider_event_id = event.get("id") or new_id("auto")
    try:
        record = ProviderEvent.objects.create(
            id=new_id("pev"),
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event.get("type", ""),
            payload=event,
        )
    except IntegrityError:
        return  # duplicate delivery — already being processed

    from apps.whatsapp.services import handle_provider_event

    try:
        handle_provider_event(record)
        record.status = ProviderEvent.Status.PROCESSED
    except Exception:
        record.status = ProviderEvent.Status.FAILED
        logger.exception("provider_event_failed id=%s", record.id)
    record.save(update_fields=["status", "updated_at"])
