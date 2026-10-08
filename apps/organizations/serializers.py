from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


class OrganizationSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code", read_only=True, default=None)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo",
            "timezone",
            "country",
            "currency",
            "status",
            "plan_code",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "status", "created_at", "updated_at"]

    def get_member_count(self, obj):
        return obj.memberships.filter(status=OrganizationMembership.Status.ACTIVE).count()


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ["id", "user", "role", "status", "joined_at", "invited_at", "created_at"]
        read_only_fields = ["id", "status", "joined_at", "invited_at", "created_at"]


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[r for r in OrganizationMembership.Role.choices if r[0] != "owner"]
    )


class InvitationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "email",
            "role",
            "status",
            "organization_name",
            "expires_at",
            "created_at",
        ]


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[r for r in OrganizationMembership.Role.choices if r[0] != "owner"]
    )


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField()
