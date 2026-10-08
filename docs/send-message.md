# Sending messages

`POST /api/v1/messages/send/` — async. The message is validated, persisted as
`queued`, and delivered by a Celery worker through the WhatsApp provider.

```json
{"bot_id": "bot_...", "to": "2557XXXXXXXX", "type": "text", "text": "Hello"}
→ 202 {"success": true, "data": {"message_id": "msg_...", "status": "queued"}, "request_id": "req_..."}
```

Types: `text`, `image`, `video`, `audio`, `document`, `sticker`, `location`,
`contact`, `interactive`. Media types require `media_url`; `caption` optional.

**Idempotency**: send `Idempotency-Key: <unique>`. Retries return the original
message (`idempotent_replay: true`, HTTP 200) instead of a duplicate.

Lifecycle: `queued → sending → sent → delivered → read` (or `failed` with
`error_code`/`error_message`). Retries use exponential backoff; permanent errors
(invalid number, unauthenticated session) fail immediately.

Status events (`message.sent` / `.delivered` / `.read` / `.failed`) arrive via
webhooks and the inbox WebSocket.
