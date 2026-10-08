"""Session lifecycle orchestration.

Views stay thin — all QR / connect / reconnect rules live here and in tasks.
Provider specifics are fully delegated to the provider abstraction.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.bots.models import Bot
from apps.common import exceptions
from apps.logs.services import emit
from apps.whatsapp.models import WhatsAppSession
from apps.whatsapp.providers import get_provider
from apps.whatsapp.providers.base import ProviderError

logger = logging.getLogger("fomobot.whatsapp")

BOT_STATE_MAP = {
    WhatsAppSession.State.CREATED: Bot.ConnectionStatus.DISCONNECTED,
    WhatsAppSession.State.CONNECTING: Bot.ConnectionStatus.CONNECTING,
    WhatsAppSession.State.QR_REQUIRED: Bot.ConnectionStatus.QR_REQUIRED,
    WhatsAppSession.State.AUTHENTICATED: Bot.ConnectionStatus.CONNECTED,
    WhatsAppSession.State.CONNECTED: Bot.ConnectionStatus.CONNECTED,
    WhatsAppSession.State.RECONNECTING: Bot.ConnectionStatus.RECONNECTING,
    WhatsAppSession.State.DISCONNECTED: Bot.ConnectionStatus.DISCONNECTED,
    WhatsAppSession.State.LOGGED_OUT: Bot.ConnectionStatus.LOGGED_OUT,
    WhatsAppSession.State.ERROR: Bot.ConnectionStatus.ERROR,
}


class WhatsAppSessionManager:
    @staticmethod
    def get_session(bot: Bot) -> WhatsAppSession | None:
        return getattr(bot, "whatsapp_session", None)

    @staticmethod
    @transaction.atomic
    def ensure_session(bot: Bot) -> WhatsAppSession:
        """Return the bot's session, creating it if needed (one per bot)."""
        session, _ = WhatsAppSession.objects.get_or_create(
            bot=bot,
            defaults={
                "organization": bot.organization,
                "provider": settings.WHATSAPP_PROVIDER,
            },
        )
        return session

    @staticmethod
    @transaction.atomic
    def request_qr(bot: Bot, *, force: bool = False) -> WhatsAppSession:
        """Produce a fresh QR code — reusing an unexpired one unless forced."""
        session = WhatsAppSessionManager.ensure_session(bot)

        if session.state == WhatsAppSession.State.CONNECTED and not force:
            raise exceptions.ConflictError(
                detail="Bot is already connected. Disconnect first to pair a new device."
            )
        if session.qr_is_fresh and not force:
            return session  # don't regenerate a still-valid QR

        WhatsAppSessionManager._guard_qr_rate(session)

        provider = get_provider(session.provider)
        session.state = WhatsAppSession.State.CONNECTING
        session.save(update_fields=["state", "updated_at"])

        try:
            provider.start_session(session)
            qr = provider.get_qr(session)
        except ProviderError as exc:
            session.state = WhatsAppSession.State.ERROR
            session.last_error = str(exc)
            session.save(update_fields=["state", "last_error", "updated_at"])
            _sync_bot(bot, session)
            raise exceptions.WhatsAppError(detail=str(exc)) from exc

        now = timezone.now()
        session.qr_code = qr.qr_data
        session.qr_expires_at = qr.expires_at
        session.qr_generated_at = now
        session.state = WhatsAppSession.State.QR_REQUIRED
        if not session.qr_window_start or now - session.qr_window_start > timedelta(hours=1):
            session.qr_window_start = now
            session.qr_regeneration_count = 0
        session.qr_regeneration_count += 1
        session.save()
        _sync_bot(bot, session)
        emit(
            "bot.qr_required",
            organization=bot.organization,
            bot=bot,
            payload={"qr_expires_at": qr.expires_at.isoformat()},
        )
        return session

    @staticmethod
    def _guard_qr_rate(session: WhatsAppSession):
        limit = settings.FOMOBOT["QR_MAX_REGENERATE_PER_HOUR"]
        if (
            session.qr_window_start
            and timezone.now() - session.qr_window_start <= timedelta(hours=1)
            and session.qr_regeneration_count >= limit
        ):
            raise exceptions.APIError(
                detail="QR regeneration limit reached. Try again later.",
                code=exceptions.ErrorCodes.RATE_LIMITED,
            )

    @staticmethod
    @transaction.atomic
    def confirm_authenticated(bot: Bot, *, phone_number: str = "") -> WhatsAppSession:
        """Provider confirmed the pairing → session connected."""
        session = WhatsAppSessionManager.ensure_session(bot)
        now = timezone.now()
        session.state = WhatsAppSession.State.CONNECTED
        session.qr_code = ""
        session.qr_expires_at = None
        session.last_connected_at = now
        session.last_heartbeat_at = now
        session.last_error = ""
        session.reconnect_attempts = 0
        session.save()
        if phone_number:
            bot.phone_number = phone_number
        bot.last_connected_at = now
        bot.last_seen_at = now
        bot.save(
            update_fields=["phone_number", "last_connected_at", "last_seen_at", "updated_at"]
        )
        _sync_bot(bot, session)
        emit(
            "bot.connected",
            organization=bot.organization,
            bot=bot,
            payload={"phone_number": bot.phone_number},
        )
        return session

    @staticmethod
    @transaction.atomic
    def disconnect(bot: Bot) -> WhatsAppSession:
        session = WhatsAppSessionManager.ensure_session(bot)
        provider = get_provider(session.provider)
        try:
            provider.disconnect(session)
        except ProviderError as exc:
            logger.warning("provider_disconnect_failed bot=%s: %s", bot.id, exc)
        session.state = WhatsAppSession.State.DISCONNECTED
        session.qr_code = ""
        session.qr_expires_at = None
        session.save()
        bot.last_disconnected_at = timezone.now()
        bot.save(update_fields=["last_disconnected_at", "updated_at"])
        _sync_bot(bot, session)
        emit("bot.disconnected", organization=bot.organization, bot=bot)
        return session

    @staticmethod
    @transaction.atomic
    def logout(bot: Bot) -> WhatsAppSession:
        """Terminate session + destroy credentials. Pairing is required again."""
        session = WhatsAppSessionManager.ensure_session(bot)
        provider = get_provider(session.provider)
        try:
            provider.logout(session)
        except ProviderError as exc:
            logger.warning("provider_logout_failed bot=%s: %s", bot.id, exc)
        session.destroy_credentials()
        session.state = WhatsAppSession.State.LOGGED_OUT
        session.qr_code = ""
        session.qr_expires_at = None
        session.save()
        bot.last_disconnected_at = timezone.now()
        bot.save(update_fields=["last_disconnected_at", "updated_at"])
        _sync_bot(bot, session)
        emit("bot.session_expired", organization=bot.organization, bot=bot)
        return session

    @staticmethod
    @transaction.atomic
    def reconnect(bot: Bot) -> WhatsAppSession:
        session = WhatsAppSessionManager.ensure_session(bot)
        max_attempts = settings.FOMOBOT["SESSION_MAX_RECONNECT_ATTEMPTS"]
        if session.reconnect_attempts >= max_attempts:
            session.state = WhatsAppSession.State.LOGGED_OUT
            session.save(update_fields=["state", "updated_at"])
            _sync_bot(bot, session)
            raise exceptions.SessionExpired(
                detail="Maximum reconnect attempts reached. Re-pair with a new QR code."
            )
        provider = get_provider(session.provider)
        session.state = WhatsAppSession.State.RECONNECTING
        session.reconnect_attempts += 1
        session.save(update_fields=["state", "reconnect_attempts", "updated_at"])
        _sync_bot(bot, session)
        try:
            status = provider.restore_session(session)
        except ProviderError as exc:
            session.state = WhatsAppSession.State.ERROR
            session.last_error = str(exc)
            session.save(update_fields=["state", "last_error", "updated_at"])
            _sync_bot(bot, session)
            raise exceptions.WhatsAppError(detail=str(exc)) from exc
        return WhatsAppSessionManager._apply_provider_status(bot, session, status)

    @staticmethod
    def _apply_provider_status(bot: Bot, session: WhatsAppSession, status) -> WhatsAppSession:
        if status.state == "connected":
            session.state = WhatsAppSession.State.CONNECTED
            session.last_connected_at = timezone.now()
            session.last_heartbeat_at = timezone.now()
            session.reconnect_attempts = 0
            if status.phone_number:
                bot.phone_number = status.phone_number
                bot.save(update_fields=["phone_number", "updated_at"])
        elif status.state in WhatsAppSession.State.values:
            session.state = status.state
        else:
            session.state = WhatsAppSession.State.ERROR
            session.last_error = f"Unknown provider state: {status.state}"
        session.save()
        _sync_bot(bot, session)
        return session

    @staticmethod
    def get_status(bot: Bot) -> dict:
        session = WhatsAppSessionManager.get_session(bot)
        return {
            "bot_id": bot.id,
            "connection_status": bot.connection_status,
            "session_state": session.state if session else None,
            "phone_number": bot.phone_number,
            "last_connected_at": bot.last_connected_at,
            "last_disconnected_at": bot.last_disconnected_at,
            "last_heartbeat_at": session.last_heartbeat_at if session else None,
            "reconnect_attempts": session.reconnect_attempts if session else 0,
        }


def handle_provider_event(record):
    """Map a deduplicated provider event onto internal state/events.

    Provider payload contract (normalized):
      {id, type, bot_id|provider_session_id, data: {...}}
    """
    from apps.messaging.services import MessageService

    payload = record.payload or {}
    data = payload.get("data", {})
    session = (
        WhatsAppSession.objects.filter(
            provider=record.provider,
            provider_session_id=payload.get("provider_session_id", ""),
        )
        .select_related("bot", "organization")
        .first()
    )
    if session is None:
        # Try direct bot_id lookup.
        from apps.bots.models import Bot

        bot = Bot.all_objects.filter(pk=payload.get("bot_id")).first()
        if bot is None:
            return
        session = WhatsAppSessionManager.ensure_session(bot)

    bot = session.bot
    if not record.organization_id:
        record.organization = bot.organization
        record.bot = bot

    event_type = payload.get("type", "")
    if event_type == "auth.authenticated":
        WhatsAppSessionManager.confirm_authenticated(
            bot, phone_number=data.get("phone_number", "")
        )
    elif event_type == "session.disconnected":
        WhatsAppSessionManager.disconnect(bot)
    elif event_type == "session.logged_out":
        WhatsAppSessionManager.logout(bot)
    elif event_type == "message.received":
        MessageService.ingest_inbound(bot=bot, data=data)
    elif event_type in ("message.delivered", "message.read", "message.failed", "message.sent"):
        MessageService.update_status_from_provider(
            bot=bot,
            provider_message_id=data.get("provider_message_id", ""),
            status=event_type.split(".", 1)[1],
            error=data.get("error", ""),
        )


def _sync_bot(bot: Bot, session: WhatsAppSession):
    """Mirror session state onto the bot's denormalized connection_status."""
    new_status = BOT_STATE_MAP.get(session.state)
    if new_status and bot.connection_status != new_status:
        bot.connection_status = new_status
        bot.save(update_fields=["connection_status", "updated_at"])
