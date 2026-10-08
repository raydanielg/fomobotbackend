# Rate limits

Defaults (configurable in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`):

| Scope | Default | Applies to |
|-------|---------|------------|
| `anon` | 60/min | any unauthenticated API traffic |
| `user` | 600/min | authenticated dashboard traffic |
| `auth` | 10/min | login, register, verify-email |
| `password_reset` | 5/hour | password reset requests |
| `send_message` | 60/min | `POST /messages/send/` |
| `qr` | 10/min | QR fetch/regeneration |
| `api` | 300/min | developer API keys (plan-aware) |

API-key traffic is limited by the organization's plan
(`limits.api_requests_per_minute` — FREE 60, PRO 300, BUSINESS 1200,
ENTERPRISE 5000), not a global constant. QR regeneration is additionally capped
at `QR_MAX_REGENERATE_PER_HOUR` per bot.

Responses return `429` with `RATE_LIMITED` and a `Retry-After` header.

Daily message volume is metered per plan (`messages_per_day`) via `UsageRecord`
counters, enforced before a message is queued.
