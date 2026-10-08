import secrets
from datetime import timedelta

from django.utils import timezone
import hashlib

from apps.admin_control.models import OTP, AdminRole, DEFAULT_ROLES, SecurityEvent
from apps.audit.models import AuditLog


def audit(request, action: str, *, target_type="", target_id="", organization=None, **metadata):
    """Append an immutable platform audit record."""
    AuditLog.objects.create(
        organization=organization,
        actor=request.user if request.user.is_authenticated else None,
        actor_email=getattr(request.user, "email", "") or "",
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        metadata=metadata,
        ip_address=_ip(request),
    )


def security_event(kind: str, *, user=None, detail="", ip=None, **metadata):
    SecurityEvent.objects.create(
        kind=kind, user=user, detail=detail, metadata=metadata, ip_address=ip
    )


def _ip(request) -> str | None:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def seed_roles() -> int:
    """Idempotently create the default admin roles."""
    created = 0
    for name, cfg in DEFAULT_ROLES.items():
        _, was_created = AdminRole.objects.get_or_create(
            name=name,
            defaults={
                "description": cfg["description"],
                "permissions": cfg["permissions"],
                "is_system": True,
            },
        )
        created += int(was_created)
    return created


def create_otp(*, identifier: str, purpose: str, channel: str, user=None, ip=None, ttl_seconds=600) -> tuple[OTP, str]:
    """Create a hashed OTP. Returns (OTP row, raw code) — raw is never persisted."""
    code = f"{secrets.randbelow(10**6):06d}"
    otp = OTP.objects.create(
        user=user,
        identifier=identifier,
        purpose=purpose,
        channel=channel,
        code_hash=hashlib.sha256(code.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
        ip_address=ip,
    )
    return otp, code


def otp_rate_limited(identifier: str, limit=5, window_seconds=3600) -> bool:
    since = timezone.now() - timedelta(seconds=window_seconds)
    return OTP.objects.filter(identifier=identifier, created_at__gte=since).count() >= limit
