"""Shared viewset base classes enforcing tenant isolation."""
from rest_framework import viewsets

from apps.common import permissions, responses
from apps.common.tenant import require_organization


class TenantViewSet(viewsets.ModelViewSet):
    """ModelViewSet that scopes every queryset to the request's organization
    and stamps ``organization`` on create.

    The tenant filter lives in ``filter_queryset`` (called by ``list`` and by
    ``get_object``), so subclass ``get_queryset`` overrides can never
    accidentally bypass isolation. Cross-tenant detail access returns 404.

    ``tenant_field`` names the model path to Organization (default
    ``organization``); override for through-models (e.g. WebhookDelivery).
    """

    permission_classes = [
        permissions.HasOrganization,
        permissions.HasOrgRole,
        permissions.HasAPIScope,
        permissions.SameOrganizationObject,
    ]
    required_roles = None  # default: read=all members, write=owner/admin/dev/agent
    required_scope = None
    tenant_field = "organization"

    def get_organization(self):
        return require_organization(self.request)

    def filter_queryset(self, queryset):
        queryset = queryset.filter(**{self.tenant_field: self.get_organization()})
        return super().filter_queryset(queryset)

    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization())

    def ok(self, data=None, status=200, **extra):
        return responses.success(data, status=status, request=self.request, **extra)
