import pytest

from apps.contacts.models import Contact
from apps.messaging.models import Message

pytestmark = pytest.mark.django_db


def test_send_message_queues_and_sends_eagerly(api_key_client, connected_bot):
    resp = api_key_client.post(
        "/api/v1/messages/send/",
        {"bot_id": connected_bot.id, "to": "+1 555 010 1010", "type": "text", "text": "Hello!"},
        format="json",
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["message_id"].startswith("msg_")

    msg = Message.objects.get(pk=data["message_id"])
    assert msg.status == "sent"  # eager celery processed it
    assert msg.provider_message_id.startswith("wamid.mock.")
    # phone normalized + contact + conversation auto-created
    assert msg.contact.phone_number == "15550101010"
    assert Contact.objects.filter(
        organization=connected_bot.organization, phone_number="15550101010"
    ).exists()


def test_send_requires_connected_bot(api_key_client, bot):
    resp = api_key_client.post(
        "/api/v1/messages/send/",
        {"bot_id": bot.id, "to": "15550101010", "type": "text", "text": "hi"},
        format="json",
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BOT_NOT_CONNECTED"


def test_idempotency_key_prevents_duplicates(api_key_client, connected_bot):
    payload = {"bot_id": connected_bot.id, "to": "15550101010", "type": "text", "text": "hi"}
    r1 = api_key_client.post(
        "/api/v1/messages/send/", payload, format="json", HTTP_IDEMPOTENCY_KEY="idem-1"
    )
    r2 = api_key_client.post(
        "/api/v1/messages/send/", payload, format="json", HTTP_IDEMPOTENCY_KEY="idem-1"
    )
    assert r1.status_code == 202 and r2.status_code == 200
    assert r1.json()["data"]["message_id"] == r2.json()["data"]["message_id"]
    assert r2.json()["data"]["idempotent_replay"] is True
    assert Message.objects.filter(organization=connected_bot.organization).count() == 1


def test_invalid_phone_rejected(api_key_client, connected_bot):
    resp = api_key_client.post(
        "/api/v1/messages/send/",
        {"bot_id": connected_bot.id, "to": "not-a-number", "type": "text", "text": "hi"},
        format="json",
    )
    assert resp.status_code == 400


def test_inbound_ingest_creates_conversation_and_is_idempotent(connected_bot):
    from apps.messaging.services import MessageService

    data = {
        "provider_message_id": "wamid.in.1",
        "from": "15551234567",
        "type": "text",
        "text": "Hi there",
        "profile_name": "Inbound User",
    }
    m1 = MessageService.ingest_inbound(bot=connected_bot, data=data)
    assert m1.direction == "inbound"
    assert m1.conversation.unread_count == 1

    # Duplicate provider delivery is dropped
    m2 = MessageService.ingest_inbound(bot=connected_bot, data=data)
    assert m2 is None
    assert Message.objects.filter(provider_message_id="wamid.in.1").count() == 1


def test_provider_status_updates(connected_bot):
    from apps.messaging.services import MessageService

    m = MessageService.ingest_inbound(
        bot=connected_bot,
        data={"provider_message_id": "wamid.in.2", "from": "15551111111", "type": "text", "text": "x"},
    )
    Message.objects.create(
        organization=connected_bot.organization,
        bot=connected_bot,
        conversation=m.conversation,
        contact=m.contact,
        direction="outbound",
        message_type="text",
        text="reply",
        status="sent",
        provider_message_id="wamid.out.1",
    )
    updated = MessageService.update_status_from_provider(
        bot=connected_bot, provider_message_id="wamid.out.1", status="read"
    )
    assert updated.status == "read"
    assert updated.read_at is not None


def test_message_list_scoped_and_paginated(api_key_client, connected_bot):
    for i in range(3):
        api_key_client.post(
            "/api/v1/messages/send/",
            {"bot_id": connected_bot.id, "to": "15550101010", "type": "text", "text": f"m{i}"},
            format="json",
        )
    resp = api_key_client.get("/api/v1/messages/?page_size=2")
    data = resp.json()["data"]
    assert data["count"] == 3
    assert len(data["results"]) == 2
    assert data["next"]
