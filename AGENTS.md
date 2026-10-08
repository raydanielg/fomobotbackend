# FomoBot backend — agent notes

Django 6 + DRF + PostgreSQL + Redis + Celery + Channels. Python 3.12+.

## Commands

- Tests: `.venv/bin/python -m pytest tests/`
- Lint: `.venv/bin/ruff check apps config tests`
- Checks: `python manage.py check` / `migrate --check`
- Server: `python manage.py runserver`; workers: `celery -A config worker -l info`,
  `celery -A config beat -l info`

## Environment quirks (this machine)

- Local PostgreSQL is on **port 5433** (Homebrew postgresql@16); port 5432 is a
  different password-protected instance. `.env` uses
  `postgres://127.0.0.1:5433/fomobot`; tests use `fomobot_test`.
- On macOS/Python 3.14 the Celery **prefork** pool hangs on this box — use
  `celery -A config worker --pool=threads` (or `=solo`) locally. Linux/Docker is
  unaffected.
- `pytest.ini` uses `config.settings.test` (eager Celery, in-memory channels,
  fixed Fernet `ENCRYPTION_KEY`, huge throttle ceilings).

## Invariants

- All org-owned viewsets subclass `common.views.TenantViewSet` — tenant filter
  is applied in `filter_queryset`; do NOT re-implement org filtering in
  `get_queryset` (it would be shadowed). Set `tenant_field` for through-models.
- Response envelope only via `common.responses.success` / exception handler.
- WhatsApp access only via `apps.whatsapp.providers.get_provider()`.
- Plan limits only via `billing.services.PlanService`.
