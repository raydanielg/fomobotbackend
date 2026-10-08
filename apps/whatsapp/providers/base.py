"""WhatsApp provider abstraction.

All WhatsApp connectivity flows through this interface. The rest of FomoBot
(services, views, tasks) never touches a provider library directly — swapping
providers means adding a new implementation and setting WHATSAPP_PROVIDER.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ProviderError(Exception):
    """Raised for transient/permanent provider failures."""

    def __init__(self, message: str, *, retryable: bool = True, code: str = ""):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass
class QRCodeResult:
    qr_data: str  # string the client renders as a QR image
    expires_at: datetime


@dataclass
class ProviderStatus:
    state: str  # maps onto WhatsAppSession.State values
    phone_number: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class SendResult:
    provider_message_id: str
    status: str = "sent"
    raw: dict = field(default_factory=dict)


class WhatsAppProvider(ABC):
    """Interface every WhatsApp backend must implement."""

    name: str = "base"

    @abstractmethod
    def start_session(self, session) -> dict:
        """Create (or attach to) a provider-side session. Returns session metadata."""

    @abstractmethod
    def get_qr(self, session) -> QRCodeResult:
        """Return a fresh pairing QR code for the session."""

    @abstractmethod
    def get_status(self, session) -> ProviderStatus: ...

    @abstractmethod
    def disconnect(self, session) -> None:
        """Gracefully disconnect; keep credentials so we can reconnect."""

    @abstractmethod
    def logout(self, session) -> None:
        """Terminate the session and invalidate credentials."""

    @abstractmethod
    def restore_session(self, session) -> ProviderStatus:
        """Restore a previously authenticated session after a restart."""

    @abstractmethod
    def send_message(
        self,
        session,
        *,
        to: str,
        message_type: str,
        text: str = "",
        media_url: str = "",
        caption: str = "",
        metadata: dict | None = None,
    ) -> SendResult: ...

    @abstractmethod
    def heartbeat(self, session) -> ProviderStatus:
        """Liveness probe used by the health-check beat task."""

    # Optional hooks --------------------------------------------------
    def get_contacts(self, session) -> list[dict[str, Any]]:
        return []

    def handle_event(self, session, event: dict) -> None:
        """Process a provider webhook/poll event."""
