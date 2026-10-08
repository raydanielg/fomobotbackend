import logging

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.conversations.models import Conversation
from apps.logs.services import emit

logger = logging.getLogger("fomobot.conversations")


class ConversationService:
    @staticmethod
    @transaction.atomic
    def get_or_create(*, bot, contact) -> tuple[Conversation, bool]:
        conversation = Conversation.objects.filter(bot=bot, contact=contact).first()
        if conversation:
            return conversation, False
        try:
            conversation = Conversation.objects.create(
                organization=bot.organization, bot=bot, contact=contact
            )
        except IntegrityError:
            conversation = Conversation.objects.get(bot=bot, contact=contact)
            return conversation, False
        emit(
            "conversation.created",
            organization=bot.organization,
            bot=bot,
            payload={"conversation_id": conversation.id, "contact_id": contact.id},
        )
        return conversation, True

    @staticmethod
    @transaction.atomic
    def record_message(conversation: Conversation, message, inbound: bool):
        conversation.last_message = message
        conversation.last_message_at = timezone.now()
        fields = ["last_message", "last_message_at", "updated_at"]
        if inbound:
            conversation.unread_count = F("unread_count") + 1
            fields.append("unread_count")
            if conversation.status == Conversation.Status.CLOSED:
                conversation.status = Conversation.Status.OPEN
                fields.append("status")
                emit(
                    "conversation.updated",
                    organization=conversation.organization,
                    bot=conversation.bot,
                    payload={"conversation_id": conversation.id, "status": "open"},
                )
        conversation.save(update_fields=fields)

    @staticmethod
    @transaction.atomic
    def mark_read(conversation: Conversation):
        conversation.unread_count = 0
        conversation.save(update_fields=["unread_count", "updated_at"])

    @staticmethod
    @transaction.atomic
    def set_status(conversation: Conversation, status: str):
        conversation.status = status
        conversation.save(update_fields=["status", "updated_at"])
        emit(
            "conversation.updated",
            organization=conversation.organization,
            bot=conversation.bot,
            payload={"conversation_id": conversation.id, "status": status},
        )

    @staticmethod
    @transaction.atomic
    def assign(conversation: Conversation, user=None):
        conversation.assigned_user = user
        conversation.save(update_fields=["assigned_user", "updated_at"])
