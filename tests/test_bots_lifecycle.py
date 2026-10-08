import pytest

from apps.bots.models import Bot
from apps.whatsapp.models import WhatsAppSession

pytestmark = pytest.mark.django_db


def test_create_bot(auth_client):
    resp = auth_client.post("/api/v1/bots/", {"name": "Sales Bot"}, format="json")
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["id"].startswith("bot_")
    assert data["connection_status"] == "disconnected"
    assert data["slug"] == "sales-bot"


def test_bot_plan_limit(auth_client, org):
    # FREE plan allows 2 bots
    for i in range(2):
        Bot.objects.create(organization=org, name=f"B{i}")
    resp = auth_client.post("/api/v1/bots/", {"name": "B3"}, format="json")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PLAN_LIMIT_REACHED"


def test_connect_produces_qr(auth_client, bot):
    resp = auth_client.post(f"/api/v1/bots/{bot.id}/connect/")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["state"] == "qr_required"
    assert data["qr"].startswith("fomobot-qr:")
    bot.refresh_from_db()
    assert bot.connection_status == "qr_required"


def test_qr_is_not_regenerated_while_fresh(auth_client, bot):
    auth_client.post(f"/api/v1/bots/{bot.id}/connect/")
    s1 = WhatsAppSession.objects.get(bot=bot)
    resp = auth_client.get(f"/api/v1/bots/{bot.id}/qr/")
    assert resp.json()["data"]["qr"] == s1.qr_code


def test_full_pairing_flow(auth_client, bot):
    auth_client.post(f"/api/v1/bots/{bot.id}/connect/")
    resp = auth_client.post(f"/api/v1/bots/{bot.id}/qr/simulate-scan/")
    assert resp.status_code == 200
    bot.refresh_from_db()
    assert bot.connection_status == "connected"
    session = WhatsAppSession.objects.get(bot=bot)
    assert session.state == "connected"
    assert session.credentials_encrypted  # encrypted at rest
    assert "mock_token" not in session.credentials_encrypted  # ciphertext only


def test_disconnect(auth_client, connected_bot):
    resp = auth_client.post(f"/api/v1/bots/{connected_bot.id}/disconnect/")
    assert resp.status_code == 200
    connected_bot.refresh_from_db()
    assert connected_bot.connection_status == "disconnected"


def test_reconnect_restores_session(auth_client, connected_bot):
    auth_client.post(f"/api/v1/bots/{connected_bot.id}/disconnect/")
    resp = auth_client.post(f"/api/v1/bots/{connected_bot.id}/reconnect/")
    assert resp.status_code == 200
    connected_bot.refresh_from_db()
    assert connected_bot.connection_status == "connected"


def test_logout_destroys_credentials(auth_client, connected_bot):
    resp = auth_client.post(f"/api/v1/bots/{connected_bot.id}/logout/")
    assert resp.status_code == 200
    session = WhatsAppSession.objects.get(bot=connected_bot)
    assert session.credentials_encrypted == ""
    assert session.state == "logged_out"


def test_status_endpoint(auth_client, bot):
    resp = auth_client.get(f"/api/v1/bots/{bot.id}/status/")
    assert resp.status_code == 200
    assert resp.json()["data"]["connection_status"] == "disconnected"


def test_delete_bot_is_soft(auth_client, connected_bot):
    resp = auth_client.delete(f"/api/v1/bots/{connected_bot.id}/")
    assert resp.status_code == 200
    connected_bot.refresh_from_db()
    assert connected_bot.deleted_at is not None
    assert connected_bot.status == "deleted"
