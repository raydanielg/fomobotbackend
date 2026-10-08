# Authentication

Two credential types:

## Dashboard (JWT)

`POST /api/v1/auth/register/`, `POST /api/v1/auth/login/` → `{tokens: {access, refresh}}`.

Use `Authorization: Bearer <access>`. Refresh via `POST /api/v1/auth/refresh/`;
`POST /api/v1/auth/logout/` blacklists the refresh token.

**Tenant context**: a user may belong to several organizations. Pass
`X-Organization-ID: org_...` on org-scoped requests; otherwise your first
membership is used. The header is verified against your memberships — you can
never address another user's org.

## Developer API keys

Created in the dashboard (`POST /api/v1/api-keys/`, owner/admin only). The raw
secret (`fb_live_...` / `fb_test_...`) is shown **once**; only a keyed hash is
stored.

Use either `X-API-Key: fb_...` or `Authorization: Bearer fb_...`.
The organization is derived from the key.

Scopes (default `*`): `messages:read|write`, `contacts:read|write`,
`conversations:read|write`, `webhooks:read|write`, `bots:read|write`,
`templates:read|write`, `logs:read`. Safe methods need `:read`, mutations `:write`.
Keys support expiry, IP allow-lists, revocation and rotation.
