# Production deployment

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- Required env: `DJANGO_SECRET_KEY`, `ENCRYPTION_KEY`, `DATABASE_URL`,
  `REDIS_URL`, `CELERY_BROKER_URL`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`.
- Serve ASGI (`uvicorn` or `gunicorn -k uvicorn.workers.UvicornWorker`) so the
  `/ws/` endpoints work. Put nginx in front (`docker/nginx/default.conf`) —
  it terminates TLS, serves `/static` + `/media`, and upgrades WebSockets.
- Run ≥1 `celery -A config worker` per queue family (messages, webhooks,
  whatsapp, notifications, automations) and one `celery -A config beat`.
- Set `SENTRY_DSN` for error reporting; logs are JSON when `LOG_FORMAT=json`.
- `GET /health/` (all checks), `/health/ready/` (db+redis+provider),
  `/health/live/` (process) — point your load balancer/probes at these.
- Never set `QR_SIMULATION=true` in production; use `WHATSAPP_PROVIDER=external`
  pointed at the real gateway.

## First deploy

```bash
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser
```
