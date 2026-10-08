from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import LoginActivity
from apps.admin_control import permissions as perms
from apps.admin_control import serializers as s
from apps.admin_control import services
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
from apps.common.pagination import StandardPagination
from apps.common.responses import success
from apps.contacts.models import Contact
from apps.conversations.models import Conversation
from apps.messaging.models import Message
from apps.messaging.serializers import SendMessageSerializer
from apps.messaging.services import MessageService
from apps.notifications.models import Notification
from apps.organizations.models import Organization
from apps.webhooks.models import WebhookDelivery
from apps.whatsapp.models import WhatsAppSession
from apps.whatsapp.services import WhatsAppSessionManager

User = get_user_model()


class AdminViewSet(viewsets.ModelViewSet):
    """Base admin viewset — staff-gated, paginated envelope, auditable."""

    permission_classes = [perms.AdminPermission]
    pagination_class = StandardPagination
    lookup_field = "id"
    required_admin_perm = ""

    def ok(self, data=None, status=200):
        return success(data, status=status, request=self.request)


# ---------------------------------------------------------------- overview


class OverviewView(APIView):
    permission_classes = [perms.AdminPermission]
    required_admin_perm = "analytics.view"

    def get(self, request):
        today = timezone.now().date()
        data = {
            "users": {
                "total": User.objects.count(),
                "active_today": User.objects.filter(last_login_at__date=today).count(),
                "verified": User.objects.filter(is_email_verified=True).count(),
                "new_today": User.objects.filter(date_joined__date=today).count(),
            },
            "organizations": {"total": Organization.objects.count()},
            "bots": {
                "total": Bot.objects.count(),
                "connected": Bot.objects.filter(connection_status="connected").count(),
            },
            "sessions": {
                "active": WhatsAppSession.objects.filter(
                    state__in=["connected", "authenticated"]
                ).count(),
            },
            "messages": {
                "today": Message.objects.filter(created_at__date=today).count(),
                "failed": Message.objects.filter(status="failed").count(),
                "total": Message.objects.count(),
            },
            "webhooks": {
                "failed": WebhookDelivery.objects.filter(status="failed").count(),
            },
            "otp": {
                "today": OTP.objects.filter(created_at__date=today).count(),
            },
            "security": {
                "open_events": SecurityEvent.objects.count(),
                "failed_logins_today": LoginActivity.objects.filter(
                    result="failure", created_at__date=today
                ).count(),
            },
        }
        return success(data, request=request)


# ---------------------------------------------------------------- users


class AdminUserViewSet(AdminViewSet):
    serializer_class = s.AdminUserListSerializer
    required_admin_perm = {
        "default": "users.view",
        "suspend": "users.suspend",
        "activate": "users.update",
        "verify_email": "users.update",
        "force_logout": "security.manage",
        "impersonate": "users.impersonate",
        "reset_password": "users.update",
        "destroy": "users.delete",
        "notes": "users.view",
    }

    def get_queryset(self):
        return (
            User.objects.annotate(
                organization_count=Count("memberships", distinct=True),
                bot_count=Count("owned_organizations__bots", distinct=True),
            )
            .order_by("-date_joined")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return s.AdminUserDetailSerializer
        return s.AdminUserListSerializer

    @action(detail=True, methods=["post"])
    def suspend(self, request, id=None):
        user = self.get_object()
        reason = request.data.get("reason", "")
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        services.security_event(
            SecurityEvent.Kind.PERMISSION_CHANGE, user=user, detail=f"Suspended: {reason}",
            ip=services._ip(request),
        )
        services.audit(request, "user.suspended", target_type="user", target_id=user.id, reason=reason)
        return self.ok({"detail": "User suspended."})

    @action(detail=True, methods=["post"])
    def activate(self, request, id=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        services.audit(request, "user.activated", target_type="user", target_id=user.id)
        return self.ok({"detail": "User activated."})

    @action(detail=True, methods=["post"], url_path="verify-email")
    def verify_email(self, request, id=None):
        user = self.get_object()
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified", "updated_at"])
        services.audit(request, "user.email_verified", target_type="user", target_id=user.id)
        return self.ok({"detail": "Email marked verified."})

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, id=None):
        user = self.get_object()
        user.set_password(request.data.get("password") or User.objects.make_random_password())
        user.save(update_fields=["updated_at"])
        services.audit(request, "user.password_reset", target_type="user", target_id=user.id)
        return self.ok({"detail": "Password reset."})

    @action(detail=True, methods=["post"], url_path="force-logout")
    def force_logout(self, request, id=None):
        user = self.get_object()
        # SimpleJWT outstanding tokens are not tracked by default — lock instead.
        user.locked_until = timezone.now() + timedelta(minutes=1)
        user.save(update_fields=["locked_until", "updated_at"])
        services.audit(request, "user.force_logout", target_type="user", target_id=user.id)
        return self.ok({"detail": "User will be signed out on next refresh."})

    @action(detail=True, methods=["post"])
    def impersonate(self, request, id=None):
        target = self.get_object()
        if target.is_superuser:
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "Cannot impersonate a superuser."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh = RefreshToken.for_user(target)
        refresh["impersonated_by"] = request.user.email
        services.audit(
            request, "user.impersonated", target_type="user", target_id=target.id,
            target_email=target.email,
        )
        return self.ok({
            "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
        })

    @action(detail=True, methods=["post"])
    def notes(self, request, id=None):
        note = InternalNote.objects.create(
            subject_user=self.get_object(),
            body=request.data.get("body", ""),
            author=request.user,
        )
        services.audit(request, "user.note_added", target_type="user", target_id=id)
        return self.ok(s.InternalNoteSerializer(note).data, status=201)

    @notes.mapping.get
    def list_notes(self, request, id=None):
        qs = InternalNote.objects.filter(subject_user=self.get_object())
        return self.ok(s.InternalNoteSerializer(qs, many=True).data)

    def destroy(self, request, id=None):
        user = self.get_object()
        if user.id == request.user.id:
            return Response(
                {"success": False, "error": {"code": "INVALID_REQUEST", "message": "You cannot delete your own account."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.email = f"deleted+{user.id}@fomobot.invalid"
        user.save(update_fields=["is_active", "email", "updated_at"])
        services.audit(request, "user.deleted", target_type="user", target_id=user.id)
        return self.ok({"detail": "User deactivated and anonymized."})


# ---------------------------------------------------------------- organizations


class AdminOrgViewSet(AdminViewSet):
    serializer_class = s.AdminOrgSerializer
    required_admin_perm = {
        "default": "organizations.view",
        "suspend": "organizations.suspend",
        "activate": "organizations.update",
        "change_plan": "plans.manage",
    }

    def get_queryset(self):
        return Organization.objects.annotate(
            member_count=Count("memberships", distinct=True),
            bot_count=Count("bots", distinct=True),
        ).order_by("-created_at")

    @action(detail=True, methods=["post"])
    def suspend(self, request, id=None):
        org = self.get_object()
        org.status = "suspended"
        org.save(update_fields=["status", "updated_at"])
        services.audit(request, "org.suspended", target_type="organization", target_id=org.id, organization=org)
        return self.ok({"detail": "Organization suspended."})

    @action(detail=True, methods=["post"])
    def activate(self, request, id=None):
        org = self.get_object()
        org.status = "active"
        org.save(update_fields=["status", "updated_at"])
        services.audit(request, "org.activated", target_type="organization", target_id=org.id, organization=org)
        return self.ok({"detail": "Organization activated."})

    @action(detail=True, methods=["post"], url_path="change-plan")
    def change_plan(self, request, id=None):
        org = self.get_object()
        plan = generics.get_object_or_404(Plan, code=request.data.get("plan"))
        org.plan = plan
        org.save(update_fields=["plan", "updated_at"])
        services.audit(request, "org.plan_changed", target_type="organization", target_id=org.id, plan=plan.code)
        return self.ok({"detail": f"Plan changed to {plan.code}."})


# ---------------------------------------------------------------- bots / sessions


class AdminBotViewSet(AdminViewSet):
    serializer_class = s.AdminBotSerializer
    required_admin_perm = {
        "default": "bots.view",
        "disconnect": "bots.disconnect",
        "reconnect": "bots.reconnect",
        "logout": "bots.disconnect",
        "disable": "bots.update",
        "enable": "bots.update",
        "destroy": "bots.delete",
    }

    def get_queryset(self):
        return Bot.objects.select_related("organization", "whatsapp_session").order_by("-created_at")

    def _session(self, bot):
        return getattr(bot, "whatsapp_session", None)

    @action(detail=True, methods=["post"])
    def disconnect(self, request, id=None):
        bot = self.get_object()
        WhatsAppSessionManager.disconnect(bot=bot)
        services.audit(request, "bot.disconnected", target_type="bot", target_id=bot.id, organization=bot.organization)
        return self.ok({"detail": "Disconnect requested."})

    @action(detail=True, methods=["post"])
    def reconnect(self, request, id=None):
        bot = self.get_object()
        WhatsAppSessionManager.reconnect(bot=bot)
        services.audit(request, "bot.reconnect", target_type="bot", target_id=bot.id, organization=bot.organization)
        return self.ok({"detail": "Reconnect requested."})

    @action(detail=True, methods=["post"])
    def logout(self, request, id=None):
        bot = self.get_object()
        WhatsAppSessionManager.logout(bot=bot)
        services.audit(request, "bot.logged_out", target_type="bot", target_id=bot.id, organization=bot.organization)
        return self.ok({"detail": "Session logged out."})

    @action(detail=True, methods=["post"])
    def disable(self, request, id=None):
        bot = self.get_object()
        bot.status = "disabled"
        bot.save(update_fields=["status", "updated_at"])
        services.audit(request, "bot.disabled", target_type="bot", target_id=bot.id)
        return self.ok({"detail": "Bot disabled."})

    @action(detail=True, methods=["post"])
    def enable(self, request, id=None):
        bot = self.get_object()
        bot.status = "active"
        bot.save(update_fields=["status", "updated_at"])
        services.audit(request, "bot.enabled", target_type="bot", target_id=bot.id)
        return self.ok({"detail": "Bot enabled."})


class AdminSessionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [perms.AdminPermission]
    pagination_class = StandardPagination
    serializer_class = s.AdminSessionSerializer
    lookup_field = "id"
    required_admin_perm = "sessions.view"

    def get_queryset(self):
        return WhatsAppSession.objects.select_related("bot", "organization").order_by("-updated_at")


# ---------------------------------------------------------------- data explorers


class _ReadOnlyAdmin(AdminViewSet, viewsets.ReadOnlyModelViewSet):
    pass


class AdminMessageViewSet(_ReadOnlyAdmin):
    serializer_class = s.AdminMessageSerializer
    required_admin_perm = "messages.view"

    def get_queryset(self):
        qs = Message.objects.select_related("bot", "bot__organization").order_by("-created_at")
        bot = self.request.query_params.get("bot")
        direction = self.request.query_params.get("direction")
        status_q = self.request.query_params.get("status")
        if bot:
            qs = qs.filter(bot_id=bot)
        if direction:
            qs = qs.filter(direction=direction)
        if status_q:
            qs = qs.filter(status=status_q)
        return qs


class AdminContactViewSet(_ReadOnlyAdmin):
    serializer_class = s.AdminContactSerializer
    required_admin_perm = "contacts.view"

    def get_queryset(self):
        return Contact.objects.select_related("organization").order_by("-created_at")


class AdminConversationViewSet(_ReadOnlyAdmin):
    serializer_class = s.AdminConversationSerializer
    required_admin_perm = "messages.view"

    def get_queryset(self):
        return Conversation.objects.select_related("bot", "bot__organization").order_by("-updated_at")


class AdminAutomationViewSet(_ReadOnlyAdmin):
    serializer_class = s.AdminAutomationSerializer
    required_admin_perm = "automations.view"

    def get_queryset(self):
        return Automation.objects.select_related("organization").order_by("-created_at")


# ---------------------------------------------------------------- security / logs


class AdminAuditViewSet(_ReadOnlyAdmin):
    serializer_class = s.AdminAuditSerializer
    required_admin_perm = "audit.view"

    def get_queryset(self):
        return AuditLog.objects.order_by("-created_at")


class LoginActivityViewSet(_ReadOnlyAdmin):
    serializer_class = s.LoginActivitySerializer
    required_admin_perm = "security.manage"

    def get_queryset(self):
        qs = LoginActivity.objects.order_by("-created_at")
        if email := self.request.query_params.get("email"):
            qs = qs.filter(email__iexact=email)
        return qs[:200]


class SecurityEventViewSet(_ReadOnlyAdmin):
    serializer_class = s.SecurityEventSerializer
    required_admin_perm = "security.manage"

    def get_queryset(self):
        return SecurityEvent.objects.order_by("-created_at")


# ---------------------------------------------------------------- OTP


class OTPViewSet(_ReadOnlyAdmin):
    serializer_class = s.OTPSerializer
    required_admin_perm = "otp.view"

    def get_queryset(self):
        return OTP.objects.select_related("user").order_by("-created_at")

    @action(detail=False, methods=["get"])
    def stats(self, request):
        today = timezone.now().date()
        qs = OTP.objects.filter(created_at__date=today)
        return self.ok({
            "today": qs.count(),
            "verified": qs.filter(status="verified").count(),
            "failed": qs.filter(status="blocked").count(),
            "expired": qs.filter(status="expired").count(),
        })

    @action(detail=True, methods=["post"])
    def invalidate(self, request, id=None):
        otp = self.get_object()
        otp.status = OTP.Status.BLOCKED
        otp.save(update_fields=["status", "updated_at"])
        services.audit(request, "otp.invalidated", target_type="otp", target_id=otp.id)
        return self.ok({"detail": "OTP invalidated."})


# ---------------------------------------------------------------- notifications / announcements


class BroadcastView(APIView):
    permission_classes = [perms.AdminPermission]
    required_admin_perm = "notifications.send"

    def post(self, request):
        title = request.data.get("title", "")
        body = request.data.get("body", "")
        audience = request.data.get("audience", "all")  # all | org:<id> | user:<id>
        channel = request.data.get("channel", "in_app")

        users = User.objects.filter(is_active=True)
        if audience.startswith("org:"):
            users = users.filter(memberships__organization_id=audience[4:])
        elif audience.startswith("user:"):
            users = users.filter(id=audience[5:])

        if channel == "in_app":
            for u in users[:1000]:
                Notification.objects.create(
                    organization_id=u.memberships.first().organization_id if u.memberships.exists() else None,
                    user=u,
                    type=Notification.Type.SYSTEM,
                    title=title,
                    body=body,
                )
        services.audit(
            request, "broadcast.sent", audience=audience, channel=channel,
            recipients=users.count(), title=title,
        )
        return success(
            {"detail": "Notification sent.", "recipients": users.count()},
            request=request,
        )

    def get(self, request):
        audience = request.query_params.get("audience", "all")
        users = User.objects.filter(is_active=True)
        if audience.startswith("org:"):
            users = users.filter(memberships__organization_id=audience[4:])
        elif audience.startswith("user:"):
            users = users.filter(id=audience[5:])
        return success({"recipients": users.count()}, request=request)


class AnnouncementViewSet(viewsets.ModelViewSet):
    permission_classes = [perms.AdminPermission]
    pagination_class = StandardPagination
    serializer_class = s.AnnouncementSerializer
    lookup_field = "id"
    required_admin_perm = {"default": "notifications.view", "create": "announcements.manage",
                           "update": "announcements.manage", "partial_update": "announcements.manage",
                           "destroy": "announcements.manage", "publish": "announcements.manage"}

    def get_queryset(self):
        return Announcement.objects.order_by("-created_at")

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        services.audit(self.request, "announcement.created", target_type="announcement", target_id=obj.id)

    @action(detail=True, methods=["post"])
    def publish(self, request, id=None):
        ann = self.get_object()
        ann.status = Announcement.Status.SENT
        ann.save(update_fields=["status", "updated_at"])
        # Fan out in-app notifications
        users = User.objects.filter(is_active=True)
        for u in users[:1000]:
            Notification.objects.create(
                organization_id=u.memberships.first().organization_id if u.memberships.exists() else None,
                user=u,
                type=Notification.Type.SYSTEM,
                title=ann.title,
                body=ann.message,
            )
        ann.sent_count = users.count()
        ann.save(update_fields=["sent_count", "updated_at"])
        services.audit(request, "announcement.published", target_type="announcement", target_id=ann.id, sent=ann.sent_count)
        return self.ok({"detail": f"Announcement sent to {ann.sent_count} users."})


class FeatureFlagViewSet(viewsets.ModelViewSet):
    permission_classes = [perms.AdminPermission]
    serializer_class = s.FeatureFlagSerializer
    lookup_field = "id"
    required_admin_perm = {"default": "settings.view", "create": "flags.manage",
                           "update": "flags.manage", "partial_update": "flags.manage",
                           "destroy": "flags.manage"}

    def get_queryset(self):
        return FeatureFlag.objects.order_by("key")


# ---------------------------------------------------------------- roles / admin users


class AdminRoleViewSet(viewsets.ModelViewSet):
    permission_classes = [perms.AdminPermission]
    serializer_class = s.AdminRoleSerializer
    lookup_field = "id"
    required_admin_perm = {"default": "roles.view", "create": "roles.manage",
                           "update": "roles.manage", "partial_update": "roles.manage",
                           "destroy": "roles.manage"}

    def get_queryset(self):
        return AdminRole.objects.annotate(admin_count=Count("admins"))

    def perform_create(self, serializer):
        obj = serializer.save()
        services.audit(self.request, "role.created", target_type="role", target_id=obj.id)


class AdminUserViewSet2(viewsets.ModelViewSet):
    """Manage platform administrators."""

    permission_classes = [perms.AdminPermission]
    serializer_class = s.AdminUserSerializer
    lookup_field = "id"
    required_admin_perm = {"default": "roles.view", "create": "roles.manage",
                           "update": "roles.manage", "partial_update": "roles.manage",
                           "destroy": "roles.manage"}

    def get_queryset(self):
        return AdminUser.objects.select_related("user").prefetch_related("roles")

    def create(self, request, *args, **kwargs):
        user = generics.get_object_or_404(User, email=request.data.get("email"))
        admin, created = AdminUser.objects.get_or_create(
            user=user, defaults={"created_by": request.user}
        )
        if role_id := request.data.get("role"):
            role = generics.get_object_or_404(AdminRole, pk=role_id)
            admin.roles.add(role)
        services.audit(request, "admin.created" if created else "admin.role_assigned",
                       target_type="user", target_id=user.id)
        return self.ok(s.AdminUserSerializer(admin).data, status=201)


# ---------------------------------------------------------------- plans / health / queues


class AdminPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [perms.AdminPermission]
    serializer_class = s.AdminPlanSerializer
    lookup_field = "id"
    required_admin_perm = {"default": "settings.view", "partial_update": "plans.manage"}

    def get_queryset(self):
        return Plan.objects.order_by("code")


class AdminHealthView(APIView):
    permission_classes = [perms.IsPlatformAdmin]

    def get(self, request):
        from apps.health.views import _check_celery, _check_db, _check_redis, _check_whatsapp

        checks = {
            "api": True,
            "database": _check_db(),
            "redis": _check_redis(),
            "celery": _check_celery(),
            "whatsapp": _check_whatsapp(),
        }
        components = [
            {"name": "API", "key": "api", "status": _to_status(checks["api"])},
            {"name": "Database", "key": "database", "status": _to_status(checks["database"])},
            {"name": "Redis", "key": "redis", "status": _to_status(checks["redis"])},
            {"name": "Celery workers", "key": "celery", "status": _to_status(checks["celery"])},
            {"name": "WhatsApp gateway", "key": "whatsapp", "status": _to_status(checks["whatsapp"])},
        ]
        overall = "operational" if all(checks.values()) else "degraded"
        return success({"overall": overall, "components": components}, request=request)


def _to_status(ok: bool) -> str:
    return "operational" if ok else "down"


class QueueView(APIView):
    permission_classes = [perms.AdminPermission]
    required_admin_perm = "settings.view"

    def get(self, request):
        from config.celery import app

        try:
            inspect = app.control.inspect(timeout=1)
            active = inspect.active() or {}
            scheduled = inspect.scheduled() or {}
            reserved = inspect.reserved() or {}
            workers = list(active.keys())
            return success({
                "workers": [
                    {"name": w, "active": len(active.get(w, [])),
                     "scheduled": len(scheduled.get(w, [])),
                     "reserved": len(reserved.get(w, []))}
                    for w in workers
                ],
                "online": bool(workers),
            }, request=request)
        except Exception:
            return success({"workers": [], "online": False}, request=request)
