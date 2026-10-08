import json

import pytest

from apps.contacts.models import Contact
from apps.contacts.services import ContactService
from apps.messaging.models import Message

pytestmark = pytest.mark.django_db


def test_contact_dedupe_normalizes_phone(org):
    c1, created1 = ContactService.get_or_create(organization=org, phone_number="+1 (555) 010-1010")
    c2, created2 = ContactService.get_or_create(organization=org, phone_number="15550101010")
    assert created1 is True and created2 is False
    assert c1.id == c2.id
    assert Contact.objects.filter(organization=org).count() == 1


def test_contact_api(auth_client):
    resp = auth_client.post(
        "/api/v1/contacts/", {"phone_number": "255700112233", "name": "Kito"}, format="json"
    )
    assert resp.status_code in (200, 201)
    resp = auth_client.get("/api/v1/contacts/?search=Kito")
    assert len(resp.json()["data"]["results"]) == 1


def test_conversation_lifecycle(auth_client, connected_bot, org):
    from apps.contacts.models import Contact
    from apps.conversations.models import Conversation

    contact = Contact.objects.create(organization=org, phone_number="15550909090")
    conv = Conversation.objects.create(organization=org, bot=connected_bot, contact=contact)

    r = auth_client.post(f"/api/v1/conversations/{conv.id}/archive/")
    assert r.json()["data"]["status"] == "archived"
    r = auth_client.post(f"/api/v1/conversations/{conv.id}/reopen/")
    assert r.json()["data"]["status"] == "open"

    r = auth_client.post(
        f"/api/v1/conversations/{conv.id}/messages/send/", {"text": "agent reply"}, format="json"
    )
    assert r.status_code == 202
    msg = Message.objects.get(pk=r.json()["data"]["message_id"])
    assert msg.conversation_id == conv.id


def test_template_render(auth_client, org):
    resp = auth_client.post(
        "/api/v1/templates/",
        {"name": "welcome", "content": "Hi {{name}}, order {{order_id}} confirmed.", "status": "active"},
        format="json",
    )
    assert resp.status_code == 201
    tpl_id = resp.json()["data"]["id"]
    r = auth_client.post(
        f"/api/v1/templates/{tpl_id}/render/",
        {"variables": {"name": "Ada", "order_id": "A-1"}},
        format="json",
    )
    assert r.json()["data"]["rendered"] == "Hi Ada, order A-1 confirmed."


def test_health_endpoints(api_client):
    assert api_client.get("/health/live/").status_code == 200
    ready = api_client.get("/health/ready/")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] is True


def test_error_envelope_on_404(auth_client):
    resp = auth_client.get("/api/v1/bots/bot_doesnotexist/")
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["request_id"].startswith("req_")
    assert "traceback" not in json.dumps(body).lower()


def test_dashboard_overview(auth_client, org, connected_bot):
    resp = auth_client.get("/api/v1/dashboard/overview/")
    data = resp.json()["data"]
    assert data["bots"]["total"] == 1
    assert data["bots"]["connected"] == 1
