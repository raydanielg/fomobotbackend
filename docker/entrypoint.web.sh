#!/bin/sh
set -e

echo "Running migrations…"
python manage.py migrate --noinput

echo "Collecting static files…"
python manage.py collectstatic --noinput --clear

echo "Seeding admin roles (idempotent)…"
python manage.py shell -c "from apps.admin_control.services import seed_roles; seed_roles()" || true

echo "Starting ASGI server (uvicorn — serves Django + WebSockets)…"
exec uvicorn config.asgi:application \
  --host 0.0.0.0 --port 8000 \
  --workers "${WEB_WORKERS:-2}" \
  --proxy-headers --forwarded-allow-ips="*"
