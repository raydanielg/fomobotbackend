import hashlib
import hmac
import json
import logging
import time

from django.conf import settings

from apps.webhooks.models import Webhook, WebhookDelivery

logger = logging.getLogger("fomobot.webhooks")

MAX_RESPONSE_BODY = 2000


def build_payload(event) -> dict:
    return {
        "id": event.id,
        "type": event.event_type,
        "created_at": event.created_at.isoformat(),
        "data": event.payload,
    }


def sign(secret: str, timestamp: str, body: str) -> str:
    """HMAC-SHA256 over '<timestamp>.<body>' — receivers verify with their copy of the secret."""
    mac = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def delivery_headers(webhook, event, body: str) -> dict:
    timestamp = str(int(time.time()))
    return {
        "Content-Type": "application/json",
        "User-Agent": "FomoBot-Webhooks/1.0",
        "X-FomoBot-Signature": sign(webhook.secret, timestamp, body),
        "X-FomoBot-Timestamp": timestamp,
        "X-FomoBot-Event": event.event_type,
        "X-FomoBot-Delivery": "",  # filled by caller
        "X-FomoBot-Request-ID": event.id,
    }


class WebhookService:
    @staticmethod
    def dispatch(event) -> int:
        """Create deliveries for all matching webhooks; returns count queued."""
        from apps.webhooks.tasks import deliver_webhook

        webhooks = Webhook.objects.filter(
            organization=event.organization, status=Webhook.Status.ACTIVE
        )
        queued = 0
        for webhook in webhooks:
            if not webhook.accepts(event.event_type, event.bot_id):
                continue
            delivery, created = WebhookDelivery.objects.get_or_create(
                webhook=webhook, event=event
            )
            if created:
                deliver_webhook.delay(delivery.id)
                queued += 1
        return queued

    @staticmethod
    def perform_delivery(delivery: WebhookDelivery) -> bool:
        """Attempt HTTP delivery. Returns True on 2xx."""
        import requests

        webhook = delivery.webhook
        event = delivery.event
        body = json.dumps(build_payload(event), separators=(",", ":"))
        headers = delivery_headers(webhook, event, body)
        headers["X-FomoBot-Delivery"] = delivery.id

        delivery.attempt_count += 1
        try:
            resp = requests.post(
                webhook.url,
                data=body,
                headers=headers,
                timeout=settings.FOMOBOT["WEBHOOK_TIMEOUT_SECONDS"],
            )
            delivery.response_status = resp.status_code
            delivery.response_body = resp.text[:MAX_RESPONSE_BODY]
            if 200 <= resp.status_code < 300:
                return _mark(delivery, WebhookDelivery.Status.DELIVERED, webhook)
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                # Permanent client error — don't retry (except 429).
                _mark(delivery, WebhookDelivery.Status.FAILED, webhook, error=f"HTTP {resp.status_code}")
                return False
            return _retry(delivery, webhook, f"HTTP {resp.status_code}")
        except requests.RequestException as exc:
            delivery.error = str(exc)[:MAX_RESPONSE_BODY]
            return _retry(delivery, webhook, str(exc)[:500])

    @staticmethod
    def backoff_seconds(attempt: int) -> int:
        # 30s, 1m, 2m, 4m, ... capped at 1h
        return min(30 * (2 ** max(0, attempt - 1)), 3600)


def _mark(delivery, status, webhook, error=""):
    from django.utils import timezone

    delivery.status = status
    delivery.error = error
    delivery.next_retry_at = None
    if status == WebhookDelivery.Status.DELIVERED:
        delivery.delivered_at = timezone.now()
        webhook.consecutive_failures = 0
        webhook.save(update_fields=["consecutive_failures", "updated_at"])
    else:
        webhook.consecutive_failures += 1
        webhook.save(update_fields=["consecutive_failures", "updated_at"])
    delivery.save()
    return status == WebhookDelivery.Status.DELIVERED


def _retry(delivery, webhook, error):
    from django.utils import timezone

    max_attempts = settings.FOMOBOT["WEBHOOK_MAX_ATTEMPTS"]
    if delivery.attempt_count >= max_attempts:
        return _mark(delivery, WebhookDelivery.Status.FAILED, webhook, error=error)
    delivery.status = WebhookDelivery.Status.RETRYING
    delivery.error = error
    delivery.next_retry_at = timezone.now() + timezone.timedelta(
        seconds=WebhookService.backoff_seconds(delivery.attempt_count)
    )
    delivery.save()
    return False
