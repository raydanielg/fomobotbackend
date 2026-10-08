import hashlib
import hmac
from unittest.mock import patch

import pytest
import requests as real_requests

from apps.logs.models import Event
from apps.webhooks.models import Webhook, WebhookDelivery
from apps.webhooks.services import WebhookService, sign

pytestmark = pytest.mark.django_db


def _webhook(org, **kw):
    defaults = {
        "name": "Hook",
        "url": "https://example.com/hook",
        "secret": "whsec_testsecret",
        "subscribed_events": ["message.received"],
    }
    defaults.update(kw)
    return Webhook.objects.create(organization=org, **defaults)


def test_signature_format():
    sig = sign("secret", "1234", '{"a":1}')
    expected = hmac.new(b"secret", b'1234.{"a":1}', hashlib.sha256).hexdigest()
    assert sig == f"sha256={expected}"


def test_create_webhook_returns_secret_once(auth_client):
    resp = auth_client.post(
        "/api/v1/webhooks/",
        {"name": "h", "url": "https://example.com/x", "subscribed_events": ["*"]},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["secret"].startswith("whsec_")
    # Never returned again
    resp = auth_client.get("/api/v1/webhooks/")
    assert "secret" not in resp.json()["data"]["results"][0]


def test_webhook_limit(auth_client, org):
    for i in range(3):  # FREE allows 3
        _webhook(org, name=f"w{i}", url=f"https://example.com/{i}")
    resp = auth_client.post(
        "/api/v1/webhooks/",
        {"name": "over", "url": "https://example.com/over", "subscribed_events": ["*"]},
        format="json",
    )
    assert resp.status_code == 403


def test_dispatch_filters_by_subscription(org, bot):
    from apps.logs.services import emit

    wh = _webhook(org)
    event = emit("message.received", organization=org, bot=bot, payload={"text": "hi"})
    assert WebhookDelivery.objects.filter(webhook=wh, event=event).exists()

    # Non-matching event type → no delivery
    _webhook(org, name="only-received", url="https://e.com/2")
    event2 = Event.objects.create(
        organization=org, bot=bot, event_type="bot.connected", payload={}
    )
    count = WebhookService.dispatch(event2)
    assert count == 0
    assert not WebhookDelivery.objects.filter(event=event2).exists()


def test_delivery_success_and_headers(org):
    wh = _webhook(org)
    event = Event.objects.create(
        organization=org, event_type="message.received", payload={"text": "hi"}
    )
    delivery = WebhookDelivery.objects.create(webhook=wh, event=event)

    captured = {}

    class FakeResp:
        status_code = 200
        text = "ok"

    def fake_post(url, data, headers, timeout):
        captured.update(headers=headers, body=data, url=url)
        return FakeResp()

    with patch.object(real_requests, "post", fake_post):
        assert WebhookService.perform_delivery(delivery) is True

    delivery.refresh_from_db()
    assert delivery.status == "delivered"
    assert captured["headers"]["X-FomoBot-Event"] == "message.received"
    assert captured["headers"]["X-FomoBot-Signature"].startswith("sha256=")
    # Verify receiver-side signature check passes
    ts = captured["headers"]["X-FomoBot-Timestamp"]
    mac = hmac.new(wh.secret.encode(), f"{ts}.{captured['body']}".encode(), hashlib.sha256)
    assert captured["headers"]["X-FomoBot-Signature"] == f"sha256={mac.hexdigest()}"


def test_delivery_4xx_fails_permanently(org):
    wh = _webhook(org)
    event = Event.objects.create(organization=org, event_type="message.received", payload={})
    delivery = WebhookDelivery.objects.create(webhook=wh, event=event)

    class FakeResp:
        status_code = 404
        text = "nope"

    with patch.object(real_requests, "post", lambda *a, **k: FakeResp()):
        assert WebhookService.perform_delivery(delivery) is False
    delivery.refresh_from_db()
    assert delivery.status == "failed"
    assert delivery.next_retry_at is None


def test_delivery_5xx_schedules_retry(org):
    wh = _webhook(org)
    event = Event.objects.create(organization=org, event_type="message.received", payload={})
    delivery = WebhookDelivery.objects.create(webhook=wh, event=event)

    class FakeResp:
        status_code = 500
        text = "boom"

    with patch.object(real_requests, "post", lambda *a, **k: FakeResp()):
        WebhookService.perform_delivery(delivery)
    delivery.refresh_from_db()
    assert delivery.status == "retrying"
    assert delivery.next_retry_at is not None
