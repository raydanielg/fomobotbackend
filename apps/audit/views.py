from rest_framework import mixins, serializers
from rest_framework.viewsets import GenericViewSet

from apps.audit.models import AuditLog
from apps.common import permissions, responses
from apps.common.tenant import require_organization


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "ip_address",
            "created_at",
        ]


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    """Read-only audit trail — owner/admin only."""

    serializer_class = AuditLogSerializer
    lookup_field = "id"
    permission_classes = [permissions.HasOrganization, permissions.HasOrgRole]
    required_roles = ("owner", "admin")
    filterset_fields = ["action", "actor_email"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        return AuditLog.objects.filter(organization=require_organization(self.request))

    def retrieve(self, request, *args, **kwargs):
        return responses.success(self.get_serializer(self.get_object()).data, request=request)
