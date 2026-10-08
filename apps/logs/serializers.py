from rest_framework import serializers

from apps.logs.models import ApiRequestLog, Event


class ApiRequestLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiRequestLog
        fields = [
            "id",
            "request_id",
            "api_key",
            "endpoint",
            "method",
            "status_code",
            "ip_address",
            "user_agent",
            "response_ms",
            "error_code",
            "created_at",
        ]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "bot",
            "event_type",
            "payload",
            "processing_status",
            "retry_count",
            "created_at",
        ]
