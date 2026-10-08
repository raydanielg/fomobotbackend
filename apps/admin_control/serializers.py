from rest_framework import serializers

from apps.accounts.models import LoginActivity, User
from apps.admin_control.models import (
    AdminRole,
    AdminUser,
    Announcement,
    FeatureFlag,
    InternalNote,
    OTP,
    SecurityEvent,
)
from apps.audit.models import AuditLog
from apps.automations.models import Automation
from apps.billing.models import Plan
from apps.bots.models import Bot
from apps.contacts.models import Contact
from apps.conversations.models import Conversation
from apps.messaging.models import Message
from apps.organizations.models import Organization
from apps.whatsapp.models import WhatsAppSession


class AdminUserListSerializer(serializers.ModelSerializer):
    organization_count = serializers.IntegerField(read_only=True)
    bot_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "is_active", "is_staff", "is_email_verified", "totp_enabled",
            "last_login_at", "last_login_ip", "failed_login_attempts",
            "locked_until", "date_joined",
            "organization_count", "bot_count",
        ]
        read_only_fields = fields


class AdminUserDetailSerializer(AdminUserListSerializer):
    organizations = serializers.SerializerMethodField()
    bots = serializers.SerializerMethodField()

    class Meta(AdminUserListSerializer.Meta):
        fields = [*AdminUserListSerializer.Meta.fields, "organizations", "bots"]

    def get_organizations(self, u):
        return [
            {"id": m.organization.id, "name": m.organization.name, "role": m.role}
            for m in u.memberships.select_related("organization").all()[:10]
        ]

    def get_bots(self, u):
        return [
            {"id": b.id, "name": b.name, "status": b.connection_status}
            for b in Bot.objects.filter(organization__owner=u)[:10]
        ]


class AdminOrgSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    bot_count = serializers.IntegerField(read_only=True)
    owner_email = serializers.CharField(source="owner.email", read_only=True)
    plan_code = serializers.CharField(source="plan.code", read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "status", "country", "currency", "timezone",
            "plan_code", "owner_email", "member_count", "bot_count",
            "created_at",
        ]


class AdminBotSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_id = serializers.CharField(source="organization.id", read_only=True)
    session_state = serializers.SerializerMethodField()

    class Meta:
        model = Bot
        fields = [
            "id", "name", "slug", "phone_number", "status", "connection_status",
            "organization_id", "organization_name", "session_state",
            "last_connected_at", "last_seen_at", "created_at",
        ]

    def get_session_state(self, b):
        s = getattr(b, "whatsapp_session", None)
        return s.state if s else None


class AdminSessionSerializer(serializers.ModelSerializer):
    bot_name = serializers.CharField(source="bot.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    phone_number = serializers.CharField(source="bot.phone_number", read_only=True)

    class Meta:
        model = WhatsAppSession
        fields = [
            "id", "bot", "bot_name", "organization_name", "phone_number",
            "provider", "state", "last_heartbeat_at", "last_connected_at",
            "reconnect_attempts", "last_error", "created_at", "updated_at",
        ]


class AdminMessageSerializer(serializers.ModelSerializer):
    bot_name = serializers.CharField(source="bot.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Message
        fields = [
            "id", "bot", "bot_name", "organization", "organization_name", "conversation", "contact",
            "direction", "message_type", "provider_message_id", "text",
            "media_url", "status", "error_code", "error_message",
            "sent_at", "delivered_at", "read_at", "created_at",
        ]


class AdminAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "organization", "actor", "actor_email", "action",
            "target_type", "target_id", "metadata", "ip_address", "created_at",
        ]


class LoginActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginActivity
        fields = ["id", "user", "email", "result", "ip_address", "user_agent", "created_at"]


class SecurityEventSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = SecurityEvent
        fields = ["id", "kind", "user", "user_email", "detail", "metadata", "ip_address", "created_at"]


class OTPSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = OTP
        fields = [
            "id", "user", "user_email", "identifier", "purpose", "channel",
            "status", "attempts", "max_attempts", "expires_at", "verified_at",
            "ip_address", "created_at",
        ]


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            "id", "title", "message", "severity", "audience", "channels",
            "starts_at", "ends_at", "status", "sent_count", "created_at",
        ]
        read_only_fields = ["sent_count", "created_at"]


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = [
            "id", "key", "description", "enabled", "rollout_percent",
            "target_organizations", "target_plans", "created_at", "updated_at",
        ]


class AdminRoleSerializer(serializers.ModelSerializer):
    admin_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AdminRole
        fields = ["id", "name", "description", "permissions", "is_system", "admin_count", "created_at"]


class AdminUserSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.full_name", read_only=True)
    role_names = serializers.SerializerMethodField()

    class Meta:
        model = AdminUser
        fields = ["id", "user", "email", "name", "status", "role_names", "created_at"]

    def get_role_names(self, a):
        return [r.name for r in a.roles.all()]


class InternalNoteSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True)

    class Meta:
        model = InternalNote
        fields = ["id", "subject_user", "organization", "body", "author", "author_email", "created_at"]
        read_only_fields = ["author", "author_email", "created_at"]


class AdminPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "code", "name", "price_monthly", "price_yearly", "limits", "created_at"]
        read_only_fields = ["code", "created_at"]


class AdminContactSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Contact
        fields = [
            "id", "organization_name", "phone_number", "name", "profile_name",
            "country", "tags", "last_seen_at", "created_at",
        ]


class AdminConversationSerializer(serializers.ModelSerializer):
    bot_name = serializers.CharField(source="bot.name", read_only=True)
    organization_name = serializers.CharField(source="bot.organization.name", read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id", "bot", "bot_name", "organization_name", "contact", "status",
            "unread_count", "last_message_at", "assigned_user", "created_at",
        ]


class AdminAutomationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Automation
        fields = [
            "id", "name", "description", "organization_name", "bot",
            "trigger_type", "status", "run_count", "created_at",
        ]
