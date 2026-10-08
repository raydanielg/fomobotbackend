import logging

from celery import shared_task

logger = logging.getLogger("fomobot.notifications.tasks")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, *, to: str, subject: str, body: str):
    from django.core.mail import send_mail

    try:
        send_mail(subject, body, None, [to], fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task
def notify_bot_status(bot_id: str, connected: bool):
    from apps.bots.models import Bot
    from apps.notifications.models import Notification
    from apps.notifications.services import NotificationService

    bot = Bot.all_objects.filter(pk=bot_id).select_related("organization").first()
    if not bot:
        return
    NotificationService.notify(
        organization=bot.organization,
        type=Notification.Type.BOT_CONNECTED if connected else Notification.Type.BOT_DISCONNECTED,
        title=f"Bot {bot.name} {'connected' if connected else 'disconnected'}",
        data={"bot_id": bot.id},
    )
