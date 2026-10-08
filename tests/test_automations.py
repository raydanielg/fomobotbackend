import pytest

from apps.automations.models import (
    Automation,
    AutomationAction,
    AutomationCondition,
    AutomationRun,
)
from apps.logs.models import Event
from apps.messaging.models import Message
from apps.templates.models import MessageTemplate

pytestmark = pytest.mark.django_db


def _automation(org, bot, conditions, actions):
    a = Automation.objects.create(
        organization=org,
        bot=bot,
        name="test",
        trigger_type=Automation.Trigger.MESSAGE_RECEIVED,
        status=Automation.Status.ACTIVE,
    )
    for c in conditions:
        AutomationCondition.objects.create(automation=a, **c)
    for act in actions:
        AutomationAction.objects.create(automation=a, **act)
    return a


def _event(org, bot, text):
    return Event.objects.create(
        organization=org,
        bot=bot,
        event_type="message.received",
        payload={"text": text, "from": "15550101010", "conversation_id": "", "contact_id": ""},
    )


def test_keyword_trigger_sends_reply(org, connected_bot):
    from apps.automations.services import AutomationService

    _automation(
        org,
        connected_bot,
        [{"field": "text", "operator": "contains", "value": "price"}],
        [{"action_type": "send_message", "config": {"text": "Prices at example.com"}}],
    )
    event = _event(org, connected_bot, "what is the price?")
    AutomationService.process_event(event)

    msg = Message.objects.filter(organization=org, direction="outbound").latest("created_at")
    assert "Prices" in msg.text
    assert msg.contact.phone_number == "15550101010"
    assert AutomationRun.objects.filter(status__in=["success", "partial"]).exists()


def test_conditions_gate_actions(org, connected_bot):
    from apps.automations.services import AutomationService

    _automation(
        org,
        connected_bot,
        [{"field": "text", "operator": "contains", "value": "price"}],
        [{"action_type": "send_message", "config": {"text": "reply"}}],
    )
    event = _event(org, connected_bot, "hello no keyword")
    AutomationService.process_event(event)
    assert not Message.objects.filter(organization=org).exists()


def test_send_template_action(org, connected_bot):
    from apps.automations.services import AutomationService

    MessageTemplate.objects.create(
        organization=org, name="greet", content="Hi {{name}}!", status="active"
    )
    tpl = MessageTemplate.objects.get(name="greet")
    _automation(
        org,
        connected_bot,
        [],
        [{"action_type": "send_template", "config": {"template_id": tpl.id, "variables": {"name": "Sam"}}}],
    )
    event = _event(org, connected_bot, "hi")
    AutomationService.process_event(event)
    msg = Message.objects.filter(organization=org).latest("created_at")
    assert msg.text == "Hi Sam!"


def test_create_automation_via_api(auth_client, bot):
    resp = auth_client.post(
        "/api/v1/automations/",
        {
            "name": "auto1",
            "trigger_type": "message.received",
            "status": "active",
            "bot": bot.id,
            "conditions": [{"field": "text", "operator": "contains", "value": "hi"}],
            "actions": [{"action_type": "send_message", "config": {"text": "yo"}}],
        },
        format="json",
    )
    assert resp.status_code == 201
    a = Automation.objects.get(name="auto1")
    assert a.conditions.count() == 1 and a.actions.count() == 1
