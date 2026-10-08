from rest_framework import serializers

from apps.messaging.models import Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "bot",
            "conversation",
            "contact",
            "direction",
            "message_type",
            "provider_message_id",
            "text",
            "media_url",
            "media_type",
            "caption",
            "metadata",
            "status",
            "error_code",
            "error_message",
            "sent_at",
            "delivered_at",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class SendMessageSerializer(serializers.Serializer):
    bot_id = serializers.CharField()
    to = serializers.CharField(help_text="Recipient phone, e.g. 2557XXXXXXXX")
    type = serializers.ChoiceField(
        choices=Message.Type.choices, default=Message.Type.TEXT
    )
    text = serializers.CharField(required=False, allow_blank=True, default="")
    media_url = serializers.URLField(required=False, allow_blank=True, default="")
    caption = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        t = attrs["type"]
        if t == Message.Type.TEXT and not attrs.get("text"):
            raise serializers.ValidationError({"text": "text is required for text messages."})
        if t in (
            Message.Type.IMAGE,
            Message.Type.VIDEO,
            Message.Type.AUDIO,
            Message.Type.DOCUMENT,
            Message.Type.STICKER,
        ) and not attrs.get("media_url"):
            raise serializers.ValidationError(
                {"media_url": f"media_url is required for {t} messages."}
            )
        return attrs
