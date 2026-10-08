import logging
import re

from django.utils import timezone

from apps.automations.models import Automation, AutomationCondition, AutomationRun
from apps.common import exceptions

logger = logging.getLogger("fomobot.automations")


def resolve_field(payload: dict, dotted: str):
    node = payload
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def evaluate_condition(cond: AutomationCondition, payload: dict) -> bool:
    value = resolve_field(payload, cond.field)
    op = cond.operator
    if op == AutomationCondition.Operator.EXISTS:
        return value is not None
    if value is None:
        return False
    actual = str(value)
    expected = cond.value
    if cond.case_insensitive:
        actual, expected = actual.lower(), expected.lower()
    if op == AutomationCondition.Operator.EQUALS:
        return actual == expected
    if op == AutomationCondition.Operator.NOT_EQUALS:
        return actual != expected
    if op == AutomationCondition.Operator.CONTAINS:
        return expected in actual
    if op == AutomationCondition.Operator.NOT_CONTAINS:
        return expected not in actual
    if op == AutomationCondition.Operator.STARTS_WITH:
        return actual.startswith(expected)
    return False


class AutomationService:
    @staticmethod
    def process_event(event):
        """Run all active automations matching this event's trigger type."""
        qs = (
            Automation.objects.filter(
                organization=event.organization,
                trigger_type=event.event_type,
                status=Automation.Status.ACTIVE,
            )
            .prefetch_related("conditions", "actions")
        )
        if event.bot_id:
            qs = qs.filter(models_q_bot(event.bot_id))
        for automation in qs:
            AutomationService._run(automation, event)

    @staticmethod
    def _run(automation: Automation, event):
        conditions = list(automation.conditions.all())
        payload = event.payload or {}
        if conditions and not all(evaluate_condition(c, payload) for c in conditions):
            return
        run = AutomationRun.objects.create(
            automation=automation,
            organization=automation.organization,
            event=event,
            status=AutomationRun.Status.SUCCESS,
        )
        failures = 0
        log = []
        for action in automation.actions.all():
            try:
                note = AutomationService.execute_action(automation, action, event)
                log.append({"action": action.action_type, "ok": True, "note": note})
            except Exception as exc:
                failures += 1
                log.append({"action": action.action_type, "ok": False, "error": str(exc)[:500]})
                logger.exception("automation_action_failed run=%s", run.id)
        run.status = (
            AutomationRun.Status.SUCCESS
            if failures == 0
            else AutomationRun.Status.PARTIAL
        )
        run.log = log
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "log", "finished_at"])
        Automation.objects.filter(pk=automation.pk).update(run_count=models_F())

    @staticmethod
    def execute_action(automation: Automation, action, event) -> str:
        from apps.messaging.services import MessageService

        payload = event.payload or {}
        config = action.config or {}
        bot = event.bot
        to = payload.get("from") or payload.get("contact_phone") or ""

        if action.action_type == action.Type.SEND_MESSAGE:
            if not bot or not to:
                raise exceptions.APIError(detail="send_message requires bot and recipient.")
            MessageService.queue_outbound(
                bot=bot, to=to, text=_render(config.get("text", ""), payload)
            )
            return "message queued"

        if action.action_type == action.Type.SEND_TEMPLATE:
            from apps.templates.models import MessageTemplate

            template = MessageTemplate.objects.get(
                pk=config["template_id"], organization=automation.organization
            )
            if not bot or not to:
                raise exceptions.APIError(detail="send_template requires bot and recipient.")
            context = dict(config.get("variables", {}))
            context.setdefault("phone", to)
            if payload.get("contact_name"):
                context.setdefault("name", payload["contact_name"])
            MessageService.queue_outbound(
                bot=bot,
                to=to,
                text=template.render(_render_map(context, payload)),
            )
            return f"template {template.name} queued"

        if action.action_type == action.Type.ADD_TAG or action.action_type == action.Type.REMOVE_TAG:
            contact_id = payload.get("contact_id")
            if not contact_id:
                return "no contact in event; skipped"
            from apps.contacts.models import Contact

            contact = Contact.objects.filter(
                pk=contact_id, organization=automation.organization
            ).first()
            if not contact:
                return "contact not found; skipped"
            tag = config.get("tag", "")
            tags = list(contact.tags or [])
            if action.action_type == action.Type.ADD_TAG and tag not in tags:
                tags.append(tag)
            if action.action_type == action.Type.REMOVE_TAG and tag in tags:
                tags.remove(tag)
            contact.tags = tags
            contact.save(update_fields=["tags", "updated_at"])
            return "tags updated"

        if action.action_type == action.Type.ASSIGN_CONVERSATION:
            from apps.conversations.models import Conversation
            from apps.conversations.services import ConversationService

            conv = Conversation.objects.filter(
                pk=payload.get("conversation_id"), organization=automation.organization
            ).first()
            if conv:
                ConversationService.assign(conv, _user_or_none(config.get("user_id")))
            return "assigned"

        if action.action_type == action.Type.CALL_WEBHOOK:
            import requests

            url = config.get("url", "")
            if not url:
                raise exceptions.APIError(detail="call_webhook requires url.")
            resp = requests.post(url, json={"event": payload}, timeout=10)
            return f"external call → HTTP {resp.status_code}"

        if action.action_type == action.Type.DELAY:
            return "delay applied"  # delays between actions handled by executor ordering

        raise exceptions.APIError(detail=f"Unsupported action: {action.action_type}")


def models_q_bot(bot_id):
    from django.db.models import Q

    return Q(bot_id=bot_id) | Q(bot__isnull=True)


def models_F():
    from django.db.models import F

    return F("run_count") + 1


def _render(text: str, payload: dict) -> str:
    def repl(match):
        return str(resolve_field(payload, match.group(1)) or "")

    return re.sub(r"{{\s*([\w.]+)\s*}}", repl, text)


def _render_map(context: dict, payload: dict) -> dict:
    return {k: _render(v, payload) if isinstance(v, str) else v for k, v in context.items()}


def _user_or_none(user_id):
    if not user_id:
        return None
    from apps.accounts.models import User

    return User.objects.filter(pk=user_id).first()
