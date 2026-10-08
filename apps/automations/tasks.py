import logging

from celery import shared_task

logger = logging.getLogger("fomobot.automations.tasks")


@shared_task
def dispatch_event_to_automations(event_id: str):
    from apps.automations.services import AutomationService
    from apps.logs.models import Event

    event = Event.objects.filter(pk=event_id).select_related("organization").first()
    if event:
        AutomationService.process_event(event)


@shared_task
def execute_automation(automation_id: str, event_id: str):
    from apps.automations.models import Automation
    from apps.automations.services import AutomationService
    from apps.logs.models import Event

    automation = Automation.objects.filter(pk=automation_id).first()
    event = Event.objects.filter(pk=event_id).first()
    if automation and event:
        AutomationService._run(automation, event)
