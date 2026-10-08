# FomoBot WhatsApp Gateway

A small Node.js service that owns the real WhatsApp connection (via
[Baileys](https://github.com/WhiskeySockets/Baileys), the multi-device
WhatsApp Web protocol) and exposes a simple HTTP API that the Django
backend's `external` provider talks to.

## Contract

Django (`apps.whatsapp.providers.external`) calls this service with
`Authorization: Bearer $SERVICE_TOKEN`:

| Method | Path                       | Purpose                                 |
| ------ | -------------------------- | --------------------------------------- |
| POST   | `/sessions`                | Create session for `bot_id`, start QR   |
| GET    | `/sessions/:id`            | Session state                           |
| GET    | `/sessions/:id/qr`         | Latest WhatsApp QR payload (scan it)    |
| GET    | `/sessions/:id/status`     | `{state, phone_number}`                 |
| POST   | `/sessions/:id/disconnect` | Drop socket, keep credentials           |
| POST   | `/sessions/:id/restore`    | Re-dial with persisted credentials      |
| DELETE | `/sessions/:id`            | Logout + wipe credentials               |
| POST   | `/sessions/:id/messages`   | Send text/media message                 |
| GET    | `/health`                  | Liveness (no auth)                      |

Inbound events (auth, disconnects, inbound messages, delivery receipts)
are pushed to Django at `CALLBACK_URL + /api/v1/whatsapp/ingress/` with
the `X-FomoBot-Provider-Token` header. Events carry a UUID `id` and are
deduplicated server-side; the gateway retries failed deliveries.

## Environment

| Var             | Default            | Notes                                        |
| --------------- | ------------------ | -------------------------------------------- |
| `PORT`          | `4000`             |                                              |
| `SERVICE_TOKEN` | —                  | Must equal `WHATSAPP_SERVICE_TOKEN` in Django |
| `CALLBACK_URL`  | `http://web:8000`  | Django base URL (compose network)             |
| `AUTH_DIR`      | `/data/sessions`   | Persisted multi-device credentials            |

## Local run

```bash
npm install
SERVICE_TOKEN=dev-token CALLBACK_URL=http://localhost:8000 node src/index.js
```

Then set `WHATSAPP_PROVIDER=external`, `WHATSAPP_SERVICE_URL=http://localhost:4000`
and the same `WHATSAPP_SERVICE_TOKEN` in the backend `.env`.

## Notes

- Sessions persist in `AUTH_DIR` (mounted volume) and are restored on boot.
- Baileys is the unofficial WhatsApp Web client. Numbers that spam get banned
  by WhatsApp — see the Acceptable Use Policy in `/terms`.
- For guaranteed Meta-supported delivery at scale, plan a migration to the
  official WhatsApp Business Cloud API — the provider seam already exists.
