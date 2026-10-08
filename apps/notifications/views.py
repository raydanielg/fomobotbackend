from django.utils import timezone
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.serializers import ModelSerializer
from rest_framework.viewsets import GenericViewSet

from apps.common import permissions, responses
from apps.common.tenant import require_organization
from apps.notifications.models import Notification


class NotificationSerializer(ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "title", "body", "data", "read_at", "created_at"]


class NotificationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """In-app notifications for the current user/org context."""

    serializer_class = NotificationSerializer
    lookup_field = "id"
    permission_classes = [permissions.HasOrganization]
    filterset_fields = ["type"]

    def get_queryset(self):
        return Notification.objects.filter(
            organization=require_organization(self.request)
        )

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return responses.success(
            self.get_serializer(self.get_object()).data, request=request
        )

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, id=None):
        n = self.get_object()
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
        return responses.success({"detail": "Read."}, request=request)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return responses.success({"detail": "All marked read."}, request=request)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(read_at__isnull=True).count()
        return responses.success({"unread": count}, request=request)
