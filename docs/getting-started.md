# Getting started

1. Install deps: `pip install -r requirements/development.txt`
2. Copy `.env.example` → `.env`, set `DATABASE_URL`, `REDIS_URL`, `ENCRYPTION_KEY`.
3. `python manage.py migrate`
4. `python manage.py seed_demo` — creates `owner@demo.fomobot` / `DemoPass123!`,
   a demo bot and prints a `fb_test_...` API key once.
5. `python manage.py runserver` → docs at `http://localhost:8000/api/docs/`.
6. Run workers: `celery -A config worker -l info` and `celery -A config beat -l info`.

Pair a bot (mock provider):

```bash
POST /api/v1/bots/{"id"}/connect/          # → qr payload
GET  /api/v1/bots/{"id"}/qr/               # current QR (auto-regenerates when expired)
POST /api/v1/bots/{"id"}/qr/simulate-scan/ # dev only, QR_SIMULATION=true
GET  /api/v1/bots/{"id"}/status/           # connection_status: connected
```
