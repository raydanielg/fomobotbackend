from rest_framework import serializers

from apps.webhooks.models import SUBSCRIBABLE_EVENTS, Webhook, WebhookDelivery


class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = [
            "id",
            "name",
            "url",
            "bot",
            "status",
            "subscribed_events",
            "consecutive_failures",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "consecutive_failures", "created_at", "updated_at"]

    def validate_subscribed_events(self, value):
        allowed = set(SUBSCRIBABLE_EVENTS) | {"*"}
        bad = [e for e in value if e not in allowed]
        if bad:
            raise serializers.ValidationError(f"Unknown events: {bad}")
        return value


class WebhookCreateSerializer(WebhookSerializer):
    pass


class WebhookCreatedSerializer(WebhookSerializer):
    secret = serializers.CharField()

    class Meta(WebhookSerializer.Meta):
        fields = [*WebhookSerializer.Meta.fields, "secret"]


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "webhook",
            "event",
            "status",
            "attempt_count",
            "response_status",
            "error",
            "next_retry_at",
            "delivered_at",
            "created_at",
        ]
