import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.encryption import hash_secret
from apps.common.models import SoftDeleteModel

VALID_SCOPES = {
    "messages:read",
    "messages:write",
    "contacts:read",
    "contacts:write",
    "conversations:read",
    "conversations:write",
    "webhooks:read",
    "webhooks:write",
    "bots:read",
    "bots:write",
    "logs:read",
    "templates:read",
    "templates:write",
    "*",
}


class APIKey(SoftDeleteModel):
    """Developer API credential.

    The raw secret is shown ONCE at creation; only a keyed hash is stored.
    Format: ``fb_live_<40 urlsafe chars>`` / ``fb_test_<...>``.
    """

    id_prefix = "key"

    class Environment(models.TextChoices):
        TEST = "test"
        LIVE = "live"

    class Status(models.TextChoices):
        ACTIVE = "active"
        REVOKED = "revoked"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="api_keys"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_api_keys",
    )
    name = models.CharField(max_length=120)
    environment = models.CharField(
        max_length=8, choices=Environment.choices, default=Environment.LIVE
    )
    prefix = models.CharField(max_length=24, db_index=True)  # e.g. "fb_live_ab12cd34"
    hashed_key = models.CharField(max_length=128, unique=True)
    scopes = models.JSONField(default=list)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    allowed_ips = models.JSONField(default=list, blank=True)  # [] = any
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"

    @property
    def is_active(self) -> bool:
        if self.status != self.Status.ACTIVE:
            return False
        return not (self.expires_at and self.expires_at <= timezone.now())

    def has_scope(self, scope: str) -> bool:
        scopes = set(self.scopes or [])
        if "*" in scopes or scope in scopes:
            return True
        resource = scope.split(":", 1)[0]
        return f"{resource}:*" in scopes

    def ip_allowed(self, ip: str) -> bool:
        return not self.allowed_ips or ip in self.allowed_ips

    @classmethod
    def generate(cls) -> tuple[str, str, str]:
        """Return (full_key, display_prefix, hash)."""
        env_prefix = settings.FOMOBOT["API_KEY_PREFIX"]
        return cls.generate_for_env(env_prefix)

    @staticmethod
    def hash_key(raw: str) -> str:
        return hash_secret(raw)


def build_key(environment: str) -> tuple[str, str, str]:
    """Return (full_key, display_prefix, hash)."""
    prefix = settings.FOMOBOT["API_KEY_PREFIX"]
    secret = secrets.token_urlsafe(30)[:40]
    full = f"{prefix}_{environment}_{secret}"
    display = full[:16]
    return full, display, hash_secret(full)
