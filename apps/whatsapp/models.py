from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class WhatsAppSession(BaseModel):
    """Persistent WhatsApp session for a Bot.

    Credentials are encrypted at rest (Fernet). The row survives restarts so
    sessions can be restored by ``restore_sessions_on_boot``.
    """

    id_prefix = "wss"

    class State(models.TextChoices):
        CREATED = "created"
        CONNECTING = "connecting"
        QR_REQUIRED = "qr_required"
        AUTHENTICATED = "authenticated"
        CONNECTED = "connected"
        RECONNECTING = "reconnecting"
        DISCONNECTED = "disconnected"
        LOGGED_OUT = "logged_out"
        ERROR = "error"

    bot = models.OneToOneField(
        "bots.Bot", on_delete=models.CASCADE, related_name="whatsapp_session"
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="wa_sessions"
    )
    provider = models.CharField(max_length=32)
    provider_session_id = models.CharField(max_length=128, blank=True, db_index=True)

    state = models.CharField(
        max_length=16, choices=State.choices, default=State.CREATED, db_index=True
    )

    credentials_encrypted = models.TextField(blank=True)
    qr_code = models.TextField(blank=True)
    qr_expires_at = models.DateTimeField(null=True, blank=True)
    qr_generated_at = models.DateTimeField(null=True, blank=True)
    qr_regeneration_count = models.PositiveIntegerField(default=0)
    qr_window_start = models.DateTimeField(null=True, blank=True)

    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    reconnect_attempts = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["state"])]

    @property
    def qr_is_fresh(self) -> bool:
        return bool(self.qr_code and self.qr_expires_at and self.qr_expires_at > timezone.now())

    @property
    def is_connected(self) -> bool:
        return self.state in (self.State.CONNECTED, self.State.AUTHENTICATED)

    def set_credentials(self, payload: dict):
        import json

        from apps.common.encryption import encrypt_str

        self.credentials_encrypted = encrypt_str(json.dumps(payload))

    def get_credentials(self) -> dict:
        import json

        from apps.common.encryption import decrypt_str

        if not self.credentials_encrypted:
            return {}
        return json.loads(decrypt_str(self.credentials_encrypted))

    def destroy_credentials(self):
        self.credentials_encrypted = ""


class ProviderEvent(BaseModel):
    """Deduplicated provider events — guarantees idempotent processing."""

    id_prefix = "pev"

    class Status(models.TextChoices):
        RECEIVED = "received"
        PROCESSED = "processed"
        DUPLICATE = "duplicate"
        FAILED = "failed"

    provider = models.CharField(max_length=32)
    provider_event_id = models.CharField(max_length=128)
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.CASCADE
    )
    bot = models.ForeignKey(
        "bots.Bot", null=True, blank=True, on_delete=models.SET_NULL
    )
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.RECEIVED, db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_id"], name="uniq_provider_event"
            )
        ]
