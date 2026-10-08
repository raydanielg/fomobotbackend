from apps.common.views import TenantViewSet
from apps.logs import serializers as s
from apps.logs.models import ApiRequestLog, Event


class ApiRequestLogViewSet(TenantViewSet):
    serializer_class = s.ApiRequestLogSerializer
    lookup_field = "id"
    required_scope = "logs"
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["status_code", "method", "api_key"]
    ordering_fields = ["created_at", "response_ms"]

    def get_queryset(self):
        return ApiRequestLog.objects.select_related("api_key")

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)


class EventViewSet(TenantViewSet):
    serializer_class = s.EventSerializer
    lookup_field = "id"
    required_scope = "logs"
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["event_type", "bot", "processing_status"]

    def get_queryset(self):
        return Event.objects.select_related("bot")

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)
