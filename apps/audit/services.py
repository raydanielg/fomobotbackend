import logging

from apps.audit.models import AuditLog

logger = logging.getLogger("fomobot.audit")


class AuditService:
    @staticmethod
    def log(*, action, organization=None, actor=None, target=None, metadata=None, ip=None):
        try:
            AuditLog.objects.create(
                organization=organization,
                actor=actor if getattr(actor, "pk", None) else None,
                actor_email=getattr(actor, "email", "") or "",
                action=action,
                target_type=target.__class__.__name__ if target else "",
                target_id=str(getattr(target, "pk", "") or ""),
                metadata=metadata or {},
                ip_address=ip,
            )
        except Exception:
            logger.exception("audit_write_failed action=%s", action)
