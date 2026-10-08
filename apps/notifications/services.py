import logging

from django.core.mail import send_mail

from apps.notifications.models import Notification

logger = logging.getLogger("fomobot.notifications")


class NotificationService:
    """In-app + email notifications. Providers (SES, Twilio SMS, etc.) plug in
    behind ``send_email``/``send_sms`` without callers changing."""

    @staticmethod
    def notify(*, organization, type, title, body="", data=None, user=None) -> Notification:
        notification = Notification.objects.create(
            organization=organization,
            user=user,
            type=type,
            title=title,
            body=body,
            data=data or {},
        )
        return notification

    @staticmethod
    def send_email(*, to: str, subject: str, body: str):
        from apps.notifications.tasks import send_email_task

        send_email_task.delay(to=to, subject=subject, body=body)

    @staticmethod
    def send_email_sync(*, to: str, subject: str, body: str):
        try:
            send_mail(subject, body, None, [to], fail_silently=False)
        except Exception:
            logger.exception("email_send_failed to=%s", to)
