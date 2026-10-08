# FomoBot Backend

Production-grade WhatsApp Bot-as-a-Service backend: Django + DRF + PostgreSQL +
Redis + Celery + Channels.

Users register, create organizations (workspaces), create WhatsApp bots, pair a
phone by QR code, then send/receive messages via a versioned developer API with
scoped API keys, webhooks, automations, templates and a realtime inbox.

## Architecture

```
                 ┌─────────────┐     ┌─────────────────┐
 Next.js front → │ Django REST │────▶│  PostgreSQL     │
 / developers  → │ /api/v1/    │     │  (all state)    │
                 └────┬────────┘     └─────────────────┘
                      │ enqueue
                 ┌────▼────────┐     ┌─────────────────┐
                 │ Celery +    │────▶│ WhatsAppProvider│
                 │ Redis       │     │ (mock|external) │
                 └────┬────────┘     └─────────────────┘
                      │ group_send
                 ┌────▼────────┐
                 │ Channels WS │  /ws/orgs/<org>/inbox/
                 └─────────────┘
```

- **Multi-tenant**: everything hangs off `Organization`; roles owner / admin /
  developer / agent / viewer. Tenant context is derived from JWT memberships or
  the API key — never from client-supplied org IDs without verification.
- **Provider abstraction**: `apps/whatsapp/providers/` — `WhatsAppProvider`
  interface (`start_session`, `get_qr`, `send_message`, `restore_session`, …)
  with `MockProvider` (dev/test) and `ExternalHTTPProvider` (talks to a WhatsApp
  gateway microservice over `WHATSAPP_SERVICE_URL`).
- **Events**: provider events are deduplicated (`ProviderEvent`), normalized into
  `Event` rows and fanned out to webhooks, automations and the realtime inbox.
- **Plans**: free by default; all limits flow through `billing.PlanService`.

## Layout

```
config/                 settings split (base/development/production/test), urls, asgi, wsgi, celery
apps/
  accounts              users, JWT auth, login activity
  organizations         orgs, memberships, invitations, roles
  billing               plans, subscriptions, usage, invoices (scaffold)
  bots                  bot CRUD + connection lifecycle endpoints
  whatsapp              session model, provider abstraction, QR flow, tasks
  api_keys              hashed API credentials, scopes, IP restrictions
  contacts / conversations / messaging   inbox data plane
  webhooks              endpoints, HMAC delivery, retries, delivery log
  automations           trigger → condition → action engine
  templates             {{variable}} message templates
  logs                  normalized events + API request logs
  notifications / audit / dashboard / health / common
tests/                  pytest suite (tenant isolation, auth, lifecycle…)
docker/                 nginx conf; compose file at repo root
docs/                   developer docs
requirements/           base / development / production pins
```

## Local development (no Docker)

Requirements: Python 3.12+, PostgreSQL, Redis.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/development.txt
cp .env.example .env          # edit DATABASE_URL etc.
createdb fomobot              # or: psql -c "CREATE DATABASE fomobot"
python manage.py migrate
python manage.py seed_demo    # demo org, users, bot, API key (printed once)
python manage.py runserver    # http://localhost:8000/api/docs/
```

Workers (in two more shells):

```bash
celery -A config worker -l info -Q default,messages,webhooks,whatsapp,notifications,automations
celery -A config beat -l info
```

> macOS note: if the prefork pool hangs, run the worker with
> `--pool=threads` (or set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`).

## Docker

```bash
docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py createsuperuser
```

## Tests

```bash
pytest                      # 68 tests incl. tenant isolation
python manage.py check      # Django system checks
```

## API quickstart

```bash
# 1. Register (creates an org you own)
curl -X POST localhost:8000/api/v1/auth/register/ -H 'Content-Type: application/json' \
  -d '{"email":"me@x.com","password":"Str0ng!Pass","organization_name":"Acme"}'

# 2. Create a bot, connect, scan the (mock) QR
curl -X POST localhost:8000/api/v1/bots/ -H "Authorization: Bearer $JWT" -H "X-Organization-ID: $ORG" -d '{"name":"Support"}'

# 3. Send a message with an API key
curl -X POST localhost:8000/api/v1/messages/send/ \
  -H "X-API-Key: fb_test_..." -H "Idempotency-Key: order-42" \
  -d '{"bot_id":"bot_...","to":"2557XXXXXXXX","type":"text","text":"Hello"}'
```

Response envelope is always `{"success": ..., "data"|"error": ..., "request_id": "req_..."}`.

See `docs/` for endpoint docs, webhook signing, error codes and rate limits.

## Environment

All configuration is via env vars — see `.env.example`. Never commit real
secrets. `ENCRYPTION_KEY` is a Fernet key encrypting WhatsApp session
credentials at rest (required in production):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## WhatsApp provider

- `WHATSAPP_PROVIDER=mock` — simulated pairing; `QR_SIMULATION=true` enables the
  dev `qr/simulate-scan/` endpoint.
- `WHATSAPP_PROVIDER=external` — expects a gateway at `WHATSAPP_SERVICE_URL`
  exposing `/sessions`… endpoints (see `apps/whatsapp/providers/external.py`).
  Gateway pushes events to `POST /api/v1/whatsapp/ingress/` with header
  `X-FomoBot-Provider-Token`.

## Production

`config.settings.production` turns on HTTPS redirects, HSTS, secure cookies,
whitenoise static and JSON logs, and wires Sentry when `SENTRY_DSN` is set.
Run behind nginx (`docker/nginx/default.conf`), `uvicorn`/`gunicorn+uvicorn`
for ASGI so WebSockets work, and scale `worker` replicas horizontally.
