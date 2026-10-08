"""Mock WhatsApp provider for development and tests.

Simulates the full QR pairing flow without a real WhatsApp account:
- start_session: allocates a provider session id
- get_qr: returns a deterministic QR payload embedding the session id
- simulate_scan(bot, phone): dev/test hook that "scans" the QR
- send_message: returns a fake provider message id

Provider-side state is stored on the DB session's metadata, so mock sessions
survive process restarts exactly like a real provider's persisted creds.
"""
import secrets
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from apps.whatsapp.providers.base import (
    ProviderStatus,
    QRCodeResult,
    SendResult,
    WhatsAppProvider,
)


class MockProvider(WhatsAppProvider):
    name = "mock"

    def start_session(self, session) -> dict:
        if not session.provider_session_id:
            session.provider_session_id = f"mock_{secrets.token_hex(8)}"
        meta = session.metadata or {}
        meta.setdefault("mock", {})
        meta["mock"]["authenticated"] = False
        session.metadata = meta
        session.save(
            update_fields=["provider_session_id", "metadata", "updated_at"]
        )
        return {"provider_session_id": session.provider_session_id}

    def get_qr(self, session) -> QRCodeResult:
        token = secrets.token_urlsafe(24)
        meta = session.metadata or {}
        meta.setdefault("mock", {})["qr_token"] = token
        session.metadata = meta
        session.save(update_fields=["metadata", "updated_at"])
        expires = timezone.now() + timezone.timedelta(
            seconds=settings.FOMOBOT["QR_TTL_SECONDS"]
        )
        return QRCodeResult(
            qr_data=f"fomobot-qr:{session.provider_session_id}:{token}",
            expires_at=expires,
        )

    def get_status(self, session) -> ProviderStatus:
        meta = (session.metadata or {}).get("mock", {})
        if meta.get("authenticated"):
            return ProviderStatus(
                state="connected", phone_number=meta.get("phone_number", "")
            )
        return ProviderStatus(state=session.state)

    def disconnect(self, session) -> None:
        meta = session.metadata or {}
        meta.setdefault("mock", {})["authenticated"] = False
        session.metadata = meta
        session.save(update_fields=["metadata", "updated_at"])

    def logout(self, session) -> None:
        meta = session.metadata or {}
        meta["mock"] = {"authenticated": False}
        session.metadata = meta
        session.provider_session_id = ""
        session.save(update_fields=["metadata", "provider_session_id", "updated_at"])

    def restore_session(self, session) -> ProviderStatus:
        creds = session.get_credentials()
        if creds.get("mock_token"):
            return ProviderStatus(
                state="connected", phone_number=creds.get("phone_number", "")
            )
        return ProviderStatus(state="logged_out")

    def send_message(self, session, *, to, message_type, text="", media_url="", caption="", metadata=None) -> SendResult:
        if not (session.metadata or {}).get("mock", {}).get("authenticated"):
            from apps.whatsapp.providers.base import ProviderError

            raise ProviderError("Mock session is not authenticated.", retryable=False)
        return SendResult(
            provider_message_id=f"wamid.mock.{secrets.token_hex(12)}",
            status="sent",
            raw={"to": to, "type": message_type},
        )

    def heartbeat(self, session) -> ProviderStatus:
        return self.get_status(session)

    # --- Dev/test helpers ---------------------------------------------
    def simulate_scan(self, session, phone_number: str = "") -> None:
        """Pretend a user scanned the QR code in WhatsApp."""
        meta = session.metadata or {}
        meta.setdefault("mock", {})
        meta["mock"]["authenticated"] = True
        meta["mock"]["phone_number"] = phone_number or "15551234567"
        meta["mock"]["qr_token"] = ""
        session.metadata = meta
        session.set_credentials(
            {"mock_token": secrets.token_hex(16), "phone_number": meta["mock"]["phone_number"]}
        )
        session.save(update_fields=["metadata", "credentials_encrypted", "updated_at"])


def now() -> datetime:  # convenience used in tests
    return timezone.now()
