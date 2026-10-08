# Errors

All failures use the envelope:

```json
{
  "success": false,
  "error": {"code": "INVALID_REQUEST", "message": "…", "details": {}},
  "request_id": "req_..."
}
```

`details` is present on `VALIDATION_ERROR` only. Stack traces are never exposed.

| HTTP | code | meaning |
|------|------|---------|
| 400 | `INVALID_REQUEST` | malformed input |
| 400 | `VALIDATION_ERROR` | serializer field errors |
| 401 | `UNAUTHORIZED` | bad/missing credentials, revoked/expired key |
| 403 | `FORBIDDEN` | role/scope/org access denied |
| 403 | `PLAN_LIMIT_REACHED` | plan entitlement exceeded |
| 404 | `NOT_FOUND` | object missing or belongs to another org |
| 409 | `CONFLICT` | e.g. already connected, already a member |
| 409 | `BOT_NOT_CONNECTED` | send attempted while bot offline |
| 409 | `SESSION_EXPIRED` | re-pairing required |
| 429 | `RATE_LIMITED` | throttle; see `Retry-After` |
| 502 | `WHATSAPP_ERROR` | provider/gateway failure |
| 500 | `INTERNAL_ERROR` | unexpected (logged + traced) |
