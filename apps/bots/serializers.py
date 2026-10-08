from rest_framework import serializers

from apps.bots.models import Bot


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "phone_number",
            "phone_country",
            "status",
            "connection_status",
            "last_connected_at",
            "last_disconnected_at",
            "last_seen_at",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "connection_status",
            "last_connected_at",
            "last_disconnected_at",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]


class BotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = ["name", "description", "phone_number", "phone_country", "settings"]


class BotStatusSerializer(serializers.Serializer):
    bot_id = serializers.CharField()
    connection_status = serializers.CharField()
    session_state = serializers.CharField(allow_null=True)
    phone_number = serializers.CharField()
    last_connected_at = serializers.DateTimeField(allow_null=True)
    last_disconnected_at = serializers.DateTimeField(allow_null=True)
    last_heartbeat_at = serializers.DateTimeField(allow_null=True)
    reconnect_attempts = serializers.IntegerField()


class QRCodeSerializer(serializers.Serializer):
    qr = serializers.CharField()
    expires_at = serializers.DateTimeField()
    state = serializers.CharField()
