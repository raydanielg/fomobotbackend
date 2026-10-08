# FomoBot — VPS deployment (coexists with other projects)

Runs in its own Docker compose project (`fomobot` / `fomobot-web`), binds only
two host ports, and uses `sslip.io` hostnames — no other service on the VPS is
touched.

## Hostnames (sslip.io)

With VPS public IP `203.0.113.10`:

| Hostname | What |
|---|---|
| `api.203.0.113.10.sslip.io` | Django API + WebSockets |
| `app.203.0.113.10.sslip.io` | Next.js frontend |

`*.sslip.io` resolves automatically — nothing to configure in DNS.

## 1. Backend

```bash
git clone https://github.com/raydanielg/fomobotbackend.git
cd fomobotbackend
cp .env.production.example .env
```

Edit `.env` — required values:

```bash
DJANGO_SECRET_KEY=$(openssl rand -hex 50)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
POSTGRES_PASSWORD=$(openssl rand -hex 24)
DJANGO_ALLOWED_HOSTS=api.203.0.113.10.sslip.io
CORS_ALLOWED_ORIGINS=https://app.203.0.113.10.sslip.io
FRONTEND_URL=https://app.203.0.113.10.sslip.io
```

Start (isolated project name so nothing else on the box is affected):

```bash
docker compose -p fomobot -f docker-compose.prod.yml up -d --build
docker compose -p fomobot -f docker-compose.prod.yml logs -f web
```

The web container auto-runs migrations, `collectstatic`, and seeds admin roles.
Internal nginx binds `127.0.0.1:8010` → change `NGINX_PORT` in `.env` if taken.

Create the first platform admin:

```bash
docker compose -p fomobot -f docker-compose.prod.yml exec web python manage.py shell <<'PY'
from apps.accounts.models import User
from apps.admin_control.models import AdminUser, AdminRole
u = User.objects.filter(email="you@yourmail.com").first()  # or create via register
if u:
    u.is_staff = True; u.is_superuser = True; u.save()
    admin, _ = AdminUser.objects.get_or_create(user=u)
    admin.roles.add(AdminRole.objects.get(name="SUPER_ADMIN"))
    print("admin ready")
PY
```

## 2. Frontend

```bash
git clone https://github.com/raydanielg/FomoBot.git fomobot-front
cd fomobot-front
API_URL=https://api.203.0.113.10.sslip.io \
  docker compose -p fomobot-web -f docker-compose.prod.yml up -d --build
```

The frontend binds `127.0.0.1:3100`. `NEXT_PUBLIC_API_URL` is baked at build —
rebuild if the API hostname changes.

## 3. Host nginx

The VPS already runs other sites — add a NEW server block only for fomobot
hostnames (see `docker/nginx/vps-vhost.conf`):

```bash
sudo cp docker/nginx/vps-vhost.conf /etc/nginx/sites-available/fomobot
sudo sed -i 's/<VPS_IP>/203.0.113.10/g' /etc/nginx/sites-available/fomobot
sudo ln -sf /etc/nginx/sites-available/fomobot /etc/nginx/sites-enabled/fomobot
sudo nginx -t && sudo systemctl reload nginx
```

## 4. HTTPS (Let's Encrypt on sslip.io)

```bash
sudo certbot --nginx -d api.203.0.113.10.sslip.io -d app.203.0.113.10.sslip.io
```

Then set `SECURE_SSL_REDIRECT=true` in `.env` and recreate the stack:

```bash
docker compose -p fomobot -f docker-compose.prod.yml up -d
```

## 5. Verify

```bash
curl https://api.203.0.113.10.sslip.io/health/        # full component check
curl https://api.203.0.113.10.sslip.io/health/ready/  # k8s-style readiness
open https://app.203.0.113.10.sslip.io
```

## What does NOT conflict with other projects

- Containers: prefixed `fomobot-` (compose project `fomobot`)
- Ports: only `8010` (backend nginx) and `3100` (frontend) on the host
- Postgres/Redis: internal-only, no host ports published
- Networks: isolated `fomobot_default` compose network
- Volumes: `fomobot_*` prefixed

## Ops

```bash
# logs
docker compose -p fomobot -f docker-compose.prod.yml logs -f

# restart backend only
docker compose -p fomobot -f docker-compose.prod.yml restart web worker

# update deploy
git pull && docker compose -p fomobot -f docker-compose.prod.yml up -d --build

# backup database
docker compose -p fomobot -f docker-compose.prod.yml exec postgres \
  pg_dump -U fomobot fomobot > backup-$(date +%F).sql
```
