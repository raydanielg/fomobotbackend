import logging

from django.db import transaction

from apps.billing.services import PlanService
from apps.bots.models import Bot
from apps.common import exceptions

logger = logging.getLogger("fomobot.bots")


class BotService:
    @staticmethod
    @transaction.atomic
    def create_bot(*, organization, name, description="", **fields) -> Bot:
        PlanService.check_limit(
            organization,
            "max_bots",
            Bot.objects.filter(organization=organization).count(),
            noun="bots",
        )
        bot = Bot.objects.create(
            organization=organization, name=name, description=description, **fields
        )
        from apps.audit.services import AuditService

        AuditService.log(
            organization=organization, action="bot.created", target=bot
        )
        return bot

    @staticmethod
    @transaction.atomic
    def update_bot(bot: Bot, **fields) -> Bot:
        for k, v in fields.items():
            setattr(bot, k, v)
        bot.save()
        return bot

    @staticmethod
    @transaction.atomic
    def delete_bot(bot: Bot, actor=None):
        """Soft-delete the bot and tear down its WhatsApp session."""
        from apps.whatsapp.services import WhatsAppSessionManager

        session = WhatsAppSessionManager.get_session(bot)
        if session and session.is_connected:
            WhatsAppSessionManager.logout(bot)
        bot.status = Bot.Status.DELETED
        bot.save(update_fields=["status", "updated_at"])
        bot.soft_delete()
        from apps.audit.services import AuditService

        AuditService.log(actor=actor, organization=bot.organization, action="bot.deleted", target=bot)

    @staticmethod
    def connect(bot: Bot):
        if bot.status != Bot.Status.ACTIVE:
            raise exceptions.APIError(
                detail=f"Bot is {bot.status}; reactivate it before connecting."
            )
        from apps.whatsapp.services import WhatsAppSessionManager

        session = WhatsAppSessionManager.ensure_session(bot)
        if session.is_connected:
            raise exceptions.ConflictError(detail="Bot is already connected.")
        return WhatsAppSessionManager.request_qr(bot)

    @staticmethod
    def disconnect(bot: Bot):
        from apps.audit.services import AuditService
        from apps.whatsapp.services import WhatsAppSessionManager

        session = WhatsAppSessionManager.disconnect(bot)
        AuditService.log(
            organization=bot.organization, action="bot.disconnected", target=bot
        )
        return session

    @staticmethod
    def reconnect(bot: Bot):
        from apps.whatsapp.services import WhatsAppSessionManager

        return WhatsAppSessionManager.reconnect(bot)
