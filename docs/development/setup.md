# Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/development.txt
cp .env.example .env
python manage.py migrate && python manage.py seed_demo
python manage.py runserver
celery -A config worker -l info    # --pool=threads on macOS
celery -A config beat -l info
pytest
```

Conventions:

- Every org-owned model subclasses `common.models.BaseModel`/`SoftDeleteModel`
  and gets a prefixed public ID (`bot_`, `msg_`, `whk_`, …).
- Views subclass `common.views.TenantViewSet`; business logic lives in
  `*/services.py`; side effects in `*/tasks.py`.
- Respond with `common.responses.success(...)`; raise `common.exceptions.*`.
- Never log secrets; never serialize `credentials_encrypted`, `hashed_key`,
  or webhook `secret` (except the one-time create response).
- Provider calls only through `apps.whatsapp.providers.get_provider()`.
