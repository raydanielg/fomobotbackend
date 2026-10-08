import logging

from django.db import transaction

from apps.api_keys.models import APIKey, build_key

logger = logging.getLogger("fomobot.api_keys")


class APIKeyService:
    @staticmethod
    @transaction.atomic
    def create_key(*, organization, created_by, name, environment, scopes, allowed_ips=None, expires_at=None):
        full_key, display_prefix, hashed = build_key(environment)
        key = APIKey.objects.create(
            organization=organization,
            created_by=created_by,
            name=name,
            environment=environment,
            prefix=display_prefix,
            hashed_key=hashed,
            scopes=scopes,
            allowed_ips=allowed_ips or [],
            expires_at=expires_at,
        )
        from apps.audit.services import AuditService

        AuditService.log(
            actor=created_by,
            organization=organization,
            action="api_key.created",
            target=key,
            metadata={"prefix": display_prefix, "scopes": scopes},
        )
        return key, full_key

    @staticmethod
    @transaction.atomic
    def revoke(key: APIKey, actor=None):
        key.status = APIKey.Status.REVOKED
        key.save(update_fields=["status", "updated_at"])
        from apps.audit.services import AuditService

        AuditService.log(actor=actor, organization=key.organization, action="api_key.revoked", target=key)

    @staticmethod
    @transaction.atomic
    def rotate(key: APIKey, actor=None) -> tuple[APIKey, str]:
        """Create a fresh key with the same config and revoke the old one."""
        new_key, raw = APIKeyService.create_key(
            organization=key.organization,
            created_by=actor or key.created_by,
            name=f"{key.name} (rotated)",
            environment=key.environment,
            scopes=key.scopes,
            allowed_ips=key.allowed_ips,
            expires_at=key.expires_at,
        )
        APIKeyService.revoke(key, actor=actor)
        return new_key, raw
