from rest_framework import status
from rest_framework.decorators import action

from apps.api_keys import serializers as s
from apps.api_keys.models import APIKey
from apps.api_keys.services import APIKeyService
from apps.common.views import TenantViewSet


class APIKeyViewSet(TenantViewSet):
    """Manage developer API credentials.

    API-key-authenticated callers can READ keys but cannot create/revoke them —
    credential management requires a dashboard (JWT/session) user.
    """

    serializer_class = s.APIKeySerializer
    lookup_field = "id"
    required_roles = ("owner", "admin")
    filterset_fields = ["status", "environment"]
    search_fields = ["name", "prefix"]

    def get_queryset(self):
        return APIKey.objects.select_related("organization", "created_by")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request, "api_key", None) is not None:
            # Credential management is dashboard-only (never via API key).
            from apps.common import exceptions

            raise exceptions.Forbidden(
                detail="API credentials cannot manage API keys. Use a dashboard session.",
            )

    def create(self, request, *args, **kwargs):
        serializer = s.APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key, raw = APIKeyService.create_key(
            organization=self.get_organization(),
            created_by=request.user,
            **serializer.validated_data,
        )
        return self.ok(
            s.APIKeyCreatedSerializer(
                {
                    "id": key.id,
                    "api_key": raw,
                    "prefix": key.prefix,
                    "name": key.name,
                    "environment": key.environment,
                    "scopes": key.scopes,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)

    def destroy(self, request, *args, **kwargs):
        key = self.get_object()
        APIKeyService.revoke(key, actor=request.user)
        key.soft_delete()
        return self.ok({"detail": "API key revoked."})

    @action(detail=True, methods=["post"])
    def revoke(self, request, id=None):
        APIKeyService.revoke(self.get_object(), actor=request.user)
        return self.ok({"detail": "API key revoked."})

    @action(detail=True, methods=["post"])
    def rotate(self, request, id=None):
        new_key, raw = APIKeyService.rotate(self.get_object(), actor=request.user)
        return self.ok(
            s.APIKeyCreatedSerializer(
                {
                    "id": new_key.id,
                    "api_key": raw,
                    "prefix": new_key.prefix,
                    "name": new_key.name,
                    "environment": new_key.environment,
                    "scopes": new_key.scopes,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )
