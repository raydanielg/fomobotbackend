# Webhooks

`POST /api/v1/webhooks/` with `url`, `subscribed_events` (e.g.
`["message.received", "bot.disconnected"]` or `["*"]`), optional `bot` to scope
to one bot. The `secret` (`whsec_...`) is returned **once** at creation —
rotate via `POST /api/v1/webhooks/{id}/rotate-secret/`.

## Payload

```json
{
  "id": "evt_...",
  "type": "message.received",
  "created_at": "2026-01-01T00:00:00Z",
  "data": {"bot_id": "...", "message_id": "msg_...", "from": "2557...", "text": "Hi"}
}
```

## Verifying the signature

Headers: `X-FomoBot-Signature` (`sha256=<hmac>`), `X-FomoBot-Timestamp`,
`X-FomoBot-Event`, `X-FomoBot-Delivery`, `X-FomoBot-Request-ID`.

```python
import hashlib, hmac
expected = "sha256=" + hmac.new(
    SECRET.encode(), f"{ts}.{raw_body}".encode(), hashlib.sha256
).hexdigest()
hmac.compare_digest(expected, request.headers["X-FomoBot-Signature"])
```

## Delivery & retries

Non-2xx responses retry with exponential backoff (30s → 1h, up to
`WEBHOOK_MAX_ATTEMPTS`). 4xx (except 429) fail permanently. Every attempt is
stored in `WebhookDelivery` — inspect via `GET /api/v1/webhooks/{id}/deliveries/`,
replay via `POST .../deliveries/{delivery_id}/replay/`, and test connectivity
with `POST /api/v1/webhooks/{id}/test/`.

## Events

`message.received|sent|delivered|read|failed`, `bot.connected|disconnected|
qr_required|session_expired`, `contact.created|updated`,
`conversation.created|updated`, `webhook.test`.
