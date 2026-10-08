from rest_framework import serializers

from apps.api_keys.models import VALID_SCOPES, APIKey


class APIKeySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "environment",
            "prefix",
            "scopes",
            "status",
            "allowed_ips",
            "expires_at",
            "last_used_at",
            "created_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "prefix", "status", "last_used_at", "created_at"]


class APIKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    environment = serializers.ChoiceField(
        choices=APIKey.Environment.choices, default=APIKey.Environment.LIVE
    )
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=sorted(VALID_SCOPES)),
        default=lambda: ["*"],
    )
    allowed_ips = serializers.ListField(
        child=serializers.IPAddressField(), required=False, default=list
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class APIKeyCreatedSerializer(serializers.Serializer):
    """Returned once at creation — contains the raw secret."""

    id = serializers.CharField()
    api_key = serializers.CharField()
    prefix = serializers.CharField()
    name = serializers.CharField()
    environment = serializers.CharField()
    scopes = serializers.ListField(child=serializers.CharField())
