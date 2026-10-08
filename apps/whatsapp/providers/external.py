"""External WhatsApp microservice provider.

Talks to a dedicated WhatsApp gateway service (e.g. a Node.js Baileys worker)
over HTTP. The gateway owns the actual WhatsApp socket; this provider is a
thin adapter so the rest of FomoBot never depends on it.
"""
import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils import timezone

from apps.whatsapp.providers.base import (
    ProviderError,
    ProviderStatus,
    QRCodeResult,
    SendResult,
    WhatsAppProvider,
)

logger = logging.getLogger("fomobot.whatsapp.external")

TIMEOUT = 10


class ExternalHTTPProvider(WhatsAppProvider):
    name = "external"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.WHATSAPP_SERVICE_TOKEN}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return urljoin(settings.WHATSAPP_SERVICE_URL.rstrip("/") + "/", path.lstrip("/"))

    def _call(self, method: str, path: str, **kwargs) -> dict:
        try:
            resp = requests.request(
                method,
                self._url(path),
                headers=self._headers(),
                timeout=kwargs.pop("timeout", TIMEOUT),
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"WhatsApp service unreachable: {exc}") from exc
        if resp.status_code >= 500:
            raise ProviderError(f"WhatsApp service error {resp.status_code}")
        if resp.status_code >= 400:
            raise ProviderError(
                f"WhatsApp service rejected request ({resp.status_code}): {resp.text[:200]}",
                retryable=False,
            )
        return resp.json() if resp.content else {}

    def start_session(self, session) -> dict:
        if session.provider_session_id:
            data = self._call("GET", f"/sessions/{session.provider_session_id}")
            return data
        data = self._call(
            "POST", "/sessions", json={"bot_id": session.bot_id, "webhook_secret": ""}
        )
        session.provider_session_id = data["session_id"]
        session.save(update_fields=["provider_session_id", "updated_at"])
        return data

    def get_qr(self, session) -> QRCodeResult:
        data = self._call("GET", f"/sessions/{session.provider_session_id}/qr")
        expires = timezone.now() + timezone.timedelta(
            seconds=int(data.get("ttl", settings.FOMOBOT["QR_TTL_SECONDS"]))
        )
        return QRCodeResult(qr_data=data["qr"], expires_at=expires)

    def get_status(self, session) -> ProviderStatus:
        data = self._call("GET", f"/sessions/{session.provider_session_id}/status")
        return ProviderStatus(
            state=data.get("state", "disconnected"),
            phone_number=data.get("phone_number", ""),
            raw=data,
        )

    def disconnect(self, session) -> None:
        self._call("POST", f"/sessions/{session.provider_session_id}/disconnect")

    def logout(self, session) -> None:
        self._call("DELETE", f"/sessions/{session.provider_session_id}")

    def restore_session(self, session) -> ProviderStatus:
        data = self._call("POST", f"/sessions/{session.provider_session_id}/restore")
        return ProviderStatus(
            state=data.get("state", "disconnected"),
            phone_number=data.get("phone_number", ""),
            raw=data,
        )

    def send_message(self, session, *, to, message_type, text="", media_url="", caption="", metadata=None) -> SendResult:
        data = self._call(
            "POST",
            f"/sessions/{session.provider_session_id}/messages",
            json={
                "to": to,
                "type": message_type,
                "text": text,
                "media_url": media_url,
                "caption": caption,
                "metadata": metadata or {},
            },
        )
        return SendResult(
            provider_message_id=data["message_id"],
            status=data.get("status", "sent"),
            raw=data,
        )

    def heartbeat(self, session) -> ProviderStatus:
        return self.get_status(session)
