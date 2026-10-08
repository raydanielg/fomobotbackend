import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel

ALL_PERMISSIONS = [
    "users.view", "users.create", "users.update", "users.suspend",
    "users.delete", "users.impersonate",
    "organizations.view", "organizations.update", "organizations.suspend",
    "bots.view", "bots.update", "bots.disconnect", "bots.reconnect", "bots.delete",
    "sessions.view", "sessions.manage",
    "messages.view", "messages.send", "messages.delete",
    "contacts.view", "contacts.update",
    "automations.view", "automations.create", "automations.update", "automations.delete",
    "templates.view", "templates.create", "templates.update",
    "otp.view", "otp.manage",
    "notifications.view", "notifications.send",
    "webhooks.view", "webhooks.manage",
    "api.view", "api.manage",
    "logs.view", "analytics.view",
    "settings.view", "settings.manage",
    "roles.view", "roles.manage",
    "audit.view", "security.manage",
    "announcements.manage", "flags.manage", "plans.manage",
]

DEFAULT_ROLES = {
    "SUPER_ADMIN": {"description": "Full platform access.", "permissions": ["*"]},
    "PLATFORM_ADMIN": {
        "description": "Platform management — everything except role management.",
        "permissions": [p for p in ALL_PERMISSIONS if not p.startswith("roles.")],
    },
    "SUPPORT_ADMIN": {
        "description": "Users, organizations, support and messaging.",
        "permissions": [
            "users.view", "users.update", "users.suspend",
            "organizations.view", "messages.view", "messages.send",
            "contacts.view", "notifications.view", "notifications.send",
            "otp.view", "otp.manage", "templates.view", "audit.view",
        ],
    },
    "DEVELOPER_ADMIN": {
        "description": "API, bots, sessions, webhooks, logs, system tools.",
        "permissions": [
            "bots.view", "bots.update", "bots.disconnect", "bots.reconnect",
            "sessions.view", "sessions.manage", "api.view", "api.manage",
            "webhooks.view", "webhooks.manage", "logs.view", "messages.view",
            "automations.view", "templates.view", "settings.view",
        ],
    },
    "MESSAGE_ADMIN": {
        "description": "Messages, templates, notifications and automations.",
        "permissions": [
            "messages.view", "messages.send", "templates.view",
            "templates.create", "templates.update", "notifications.view",
            "notifications.send", "automations.view", "automations.create",
            "automations.update", "announcements.manage",
        ],
    },
    "SECURITY_ADMIN": {
        "description": "Security, audit logs, login activity, sessions.",
        "permissions": [
            "audit.view", "security.manage", "sessions.view", "sessions.manage",
            "users.view", "users.suspend", "otp.view", "otp.manage",
            "roles.view", "logs.view",
        ],
    },
    "ANALYTICS_ADMIN": {
        "description": "Analytics and reports.",
        "permissions": [
            "analytics.view", "users.view", "organizations.view", "bots.view",
            "messages.view", "logs.view",
        ],
    },
    "READ_ONLY_ADMIN": {
        "description": "View-only access.",
        "permissions": [p for p in ALL_PERMISSIONS if p.endswith(".view")],
    },
}


class AdminRole(BaseModel):
    """Platform-level role with a list of 'resource.action' permissions."""

    id_prefix = "rl"

    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=256, blank=True)
    permissions = models.JSONField(default=list)
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AdminUser(BaseModel):
    """Platform administrator — independent of organization membership."""

    id_prefix = "adm"

    class Status(models.TextChoices):
        ACTIVE = "active"
        SUSPENDED = "suspended"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_profile"
    )
    roles = models.ManyToManyField(AdminRole, related_name="admins", blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name="admins_created",
    )

    def has_perm(self, perm: str) -> bool:
        if self.user.is_superuser:
            return True
        perms: set[str] = set()
        for role in self.roles.all():
            perms.update(role.permissions or [])
        if "*" in perms or perm in perms:
            return True
        resource = perm.split(".", 1)[0]
        return f"{resource}.*" in perms


class OTP(BaseModel):
    """Hashed, expiring, rate-limited one-time codes."""

    id_prefix = "otp"

    class Purpose(models.TextChoices):
        REGISTER = "register"
        PHONE = "phone_verify"
        LOGIN = "login"
        PASSWORD_RESET = "password_reset"
        ACTION = "sensitive_action"

    class Channel(models.TextChoices):
        EMAIL = "email"
        WHATSAPP = "whatsapp"
        SMS = "sms"

    class Status(models.TextChoices):
        PENDING = "pending"
        VERIFIED = "verified"
        EXPIRED = "expired"
        BLOCKED = "blocked"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="otps",
    )
    identifier = models.CharField(max_length=256)  # email or phone
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    verified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["identifier", "status"])]

    def verify(self, code: str) -> bool:
        digest = hashlib.sha256(code.encode()).hexdigest()
        if self.status != self.Status.PENDING or timezone.now() > self.expires_at:
            return False
        self.attempts += 1
        if self.attempts > self.max_attempts:
            self.status = self.Status.BLOCKED
            self.save(update_fields=["attempts", "status", "updated_at"])
            return False
        if digest == self.code_hash:
            self.status = self.Status.VERIFIED
            self.verified_at = timezone.now()
            self.save(update_fields=["attempts", "status", "verified_at", "updated_at"])
            return True
        self.save(update_fields=["attempts", "updated_at"])
        return False


class Announcement(BaseModel):
    id_prefix = "ann"

    class Severity(models.TextChoices):
        INFO = "info"
        WARNING = "warning"
        CRITICAL = "critical"

    class Status(models.TextChoices):
        DRAFT = "draft"
        SCHEDULED = "scheduled"
        SENT = "sent"
        CANCELLED = "cancelled"

    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    audience = models.CharField(max_length=32, default="all")  # all | plan:<code> | org:<id>
    channels = models.JSONField(default=list)  # ["in_app", "email", "whatsapp"]
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    sent_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-created_at"]


class FeatureFlag(BaseModel):
    id_prefix = "flg"

    key = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=256, blank=True)
    enabled = models.BooleanField(default=False)
    rollout_percent = models.PositiveIntegerField(default=100)
    target_organizations = models.JSONField(default=list)
    target_plans = models.JSONField(default=list)

    class Meta:
        ordering = ["key"]

    def is_enabled_for(self, organization=None) -> bool:
        if not self.enabled:
            return False
        if organization and self.target_organizations:
            return str(organization.id) in [str(i) for i in self.target_organizations]
        return True


class InternalNote(BaseModel):
    """Admin-only notes on users/organizations. Never user-visible."""

    id_prefix = "nt"

    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="admin_notes",
    )
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True,
        on_delete=models.CASCADE, related_name="admin_notes",
    )
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="admin_notes_written",
    )

    class Meta:
        ordering = ["-created_at"]


class SecurityEvent(BaseModel):
    id_prefix = "sev"

    class Kind(models.TextChoices):
        FAILED_LOGIN = "failed_login"
        SUSPICIOUS_LOGIN = "suspicious_login"
        OTP_ABUSE = "otp_abuse"
        API_ABUSE = "api_abuse"
        RATE_LIMIT = "rate_limit"
        SESSION_FAILURE = "session_failure"
        PERMISSION_CHANGE = "permission_change"
        ADMIN_ACTION = "admin_action"

    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    detail = models.CharField(max_length=256, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
