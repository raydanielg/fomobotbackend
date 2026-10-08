import pytest
from rest_framework.test import APIClient

from apps.api_keys.models import APIKey

pytestmark = pytest.mark.django_db


def test_create_key_returns_secret_once(auth_client):
    resp = auth_client.post(
        "/api/v1/api-keys/",
        {"name": "CI", "environment": "test", "scopes": ["messages:write"]},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["api_key"].startswith("fb_test_")
    key = APIKey.objects.get(pk=data["id"])
    assert key.hashed_key != data["api_key"]  # stored hashed, not plaintext
    # Subsequent reads never include the secret:
    resp = auth_client.get(f"/api/v1/api-keys/{key.id}/")
    assert "api_key" not in resp.json()["data"]


def test_api_key_authenticates(api_key_client):
    resp = api_key_client.get("/api/v1/bots/")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_bad_api_key_rejected(api_client):
    api_client.credentials(HTTP_X_API_KEY="fb_test_bogus")
    resp = api_client.get("/api/v1/bots/")
    assert resp.status_code == 401


def test_revoked_key_rejected(api_key, api_key_client):
    from apps.api_keys.services import APIKeyService

    APIKeyService.revoke(api_key)
    resp = api_key_client.get("/api/v1/bots/")
    assert resp.status_code == 401


def test_scope_enforcement(org, user):
    from apps.api_keys.services import APIKeyService

    _, raw = APIKeyService.create_key(
        organization=org, created_by=user, name="ro",
        environment="test", scopes=["messages:read"],
    )
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=raw)

    ok = client.get("/api/v1/messages/")
    assert ok.status_code == 200

    denied = client.get("/api/v1/webhooks/")
    assert denied.status_code == 403

    denied_write = client.post(
        "/api/v1/messages/send/",
        {"bot_id": "bot_x", "to": "1555", "type": "text", "text": "hi"},
        format="json",
    )
    assert denied_write.status_code == 403


def test_ip_restriction(api_key):
    api_key.allowed_ips = ["10.0.0.1"]
    api_key.save()
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=api_key.raw)
    client.defaults["REMOTE_ADDR"] = "192.168.1.50"
    resp = client.get("/api/v1/bots/", REMOTE_ADDR="192.168.1.50")
    assert resp.status_code == 401


def test_api_keys_not_manageable_by_api_key(api_key_client):
    resp = api_key_client.get("/api/v1/api-keys/")
    assert resp.status_code == 403


def test_rotation(api_key, auth_client):
    resp = auth_client.post(f"/api/v1/api-keys/{api_key.id}/rotate/")
    assert resp.status_code == 201
    api_key.refresh_from_db()
    assert api_key.status == "revoked"


def test_request_logged(api_key_client, org):
    api_key_client.get("/api/v1/bots/")
    from apps.logs.models import ApiRequestLog

    log = ApiRequestLog.objects.filter(organization=org).latest("created_at")
    assert log.endpoint == "/api/v1/bots/"
    assert log.status_code == 200
    assert log.request_id.startswith("req_")
