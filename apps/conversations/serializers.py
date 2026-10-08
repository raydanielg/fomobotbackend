from rest_framework import serializers

from apps.contacts.serializers import ContactSerializer
from apps.conversations.models import Conversation
from apps.messaging.serializers import MessageSerializer


class ConversationSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    last_message = MessageSerializer(read_only=True)
    assigned_user_email = serializers.EmailField(
        source="assigned_user.email", read_only=True, default=None
    )
    bot_id = serializers.CharField(source="bot.id", read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "bot_id",
            "contact",
            "status",
            "labels",
            "last_message",
            "last_message_at",
            "unread_count",
            "assigned_user",
            "assigned_user_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AssignSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=False, allow_null=True)


class ReplySerializer(serializers.Serializer):
    text = serializers.CharField(max_length=4096)
