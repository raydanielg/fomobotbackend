import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.billing.services import PlanService
from apps.bots.models import Bot
from apps.common import exceptions
from apps.common.utils import normalize_phone
from apps.contacts.services import ContactService
from apps.conversations.services import ConversationService
from apps.logs.services import emit
from apps.messaging.models import Message

logger = logging.getLogger("fomobot.messaging")


class MessageService:
    @staticmethod
    @transaction.atomic
    def queue_outbound(
        *,
        bot: Bot,
        to: str,
        message_type: str = Message.Type.TEXT,
        text: str = "",
        media_url: str = "",
        caption: str = "",
        metadata: dict | None = None,
        idempotency_key: str = "",
    ) -> tuple[Message, bool]:
        """Validate → create queued message → enqueue provider send.

        Returns (message, created). Idempotent via ``Idempotency-Key``.
        """
        org = bot.organization

        if idempotency_key:
            existing = Message.objects.filter(
                organization=org, idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing, False

        if bot.connection_status != Bot.ConnectionStatus.CONNECTED:
            raise exceptions.BotNotConnected()

        daily = PlanService.usage_today(org, "messages_sent")
        PlanService.check_limit(org, "messages_per_day", daily, noun="messages/day")

        try:
            phone = normalize_phone(to)
        except ValueError as exc:
            raise exceptions.APIError(detail=str(exc)) from exc
        contact, _ = ContactService.get_or_create(organization=org, phone_number=phone)
        conversation, _ = ConversationService.get_or_create(bot=bot, contact=contact)

        try:
            message = Message.objects.create(
                organization=org,
                bot=bot,
                conversation=conversation,
                contact=contact,
                direction=Message.Direction.OUTBOUND,
                message_type=message_type,
                text=text,
                media_url=media_url,
                caption=caption,
                metadata=metadata or {},
                status=Message.Status.QUEUED,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            message = Message.objects.get(
                organization=org, idempotency_key=idempotency_key
            )
            return message, False

        ConversationService.record_message(conversation, message, inbound=False)
        PlanService.increment_usage(org, "messages_sent")

        from apps.messaging.tasks import process_outbound_message

        process_outbound_message.delay(message.id)
        return message, True

    @staticmethod
    @transaction.atomic
    def ingest_inbound(*, bot: Bot, data: dict) -> Message | None:
        """Persist a provider-pushed inbound message. Idempotent on provider id."""
        provider_id = data.get("provider_message_id") or data.get("id") or ""
        if provider_id and Message.objects.filter(
            bot=bot, provider_message_id=provider_id
        ).exists():
            return None  # duplicate delivery

        contact, _ = ContactService.get_or_create(
            organization=bot.organization,
            phone_number=data.get("from", ""),
            defaults={"profile_name": data.get("profile_name", "")},
        )
        conversation, _ = ConversationService.get_or_create(bot=bot, contact=contact)

        message = Message.objects.create(
            organization=bot.organization,
            bot=bot,
            conversation=conversation,
            contact=contact,
            direction=Message.Direction.INBOUND,
            message_type=data.get("type", Message.Type.TEXT),
            provider_message_id=provider_id,
            text=data.get("text", ""),
            media_url=data.get("media_url", ""),
            media_type=data.get("media_type", ""),
            caption=data.get("caption", ""),
            metadata=data.get("metadata", {}),
            status=Message.Status.DELIVERED,
            sent_at=data.get("sent_at") or timezone.now(),
            delivered_at=timezone.now(),
        )
        ConversationService.record_message(conversation, message, inbound=True)
        emit(
            "message.received",
            organization=bot.organization,
            bot=bot,
            payload={
                "message_id": message.id,
                "conversation_id": conversation.id,
                "from": contact.phone_number,
                "type": message.message_type,
                "text": message.text,
            },
        )
        return message

    @staticmethod
    @transaction.atomic
    def update_status_from_provider(*, bot: Bot, provider_message_id: str, status: str, error: str = ""):
        message = (
            Message.objects.filter(bot=bot, provider_message_id=provider_message_id)
            .select_for_update()
            .first()
        )
        if not message:
            return None
        now = timezone.now()
        if status == "delivered":
            message.status = Message.Status.DELIVERED
            message.delivered_at = now
        elif status == "read":
            message.status = Message.Status.READ
            message.read_at = now
            message.delivered_at = message.delivered_at or now
        elif status == "sent":
            message.status = Message.Status.SENT
            message.sent_at = message.sent_at or now
        elif status == "failed":
            message.status = Message.Status.FAILED
            message.error_message = error
        else:
            return None
        message.save()
        emit(
            f"message.{status}",
            organization=message.organization,
            bot=bot,
            payload={
                "message_id": message.id,
                "conversation_id": message.conversation_id,
                "status": status,
                "error": error,
            },
        )
        return message

    @staticmethod
    def mark_failed(message: Message, error: str, code: str = ""):
        message.status = Message.Status.FAILED
        message.error_message = error[:2000]
        message.error_code = code
        message.save(
            update_fields=["status", "error_message", "error_code", "updated_at"]
        )
        emit(
            "message.failed",
            organization=message.organization,
            bot=message.bot,
            payload={"message_id": message.id, "error": message.error_message},
        )
