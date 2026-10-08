"""DRF authentication for developer API keys.

Credentials are accepted via ``Authorization: Bearer fb_live_...`` or the
``X-API-Key`` header. Only the hash is stored, so lookup is hash-equality.
"""
import logging

from django.utils import timezone
from rest_framework import exceptions as drf_exc
from rest_framework.authentication import BaseAuthentication

from apps.api_keys.models import APIKey
from apps.common.middleware import _client_ip

logger = logging.getLogger("fomobot.api_keys")


class APIKeyAuthentication(BaseAuthentication):
    keyword_prefix = "fb_"

    def authenticate(self, request):
        raw = self._extract(request)
        if not raw:
            return None

        try:
            key = APIKey.objects.select_related("organization", "created_by").get(
                hashed_key=APIKey.hash_key(raw)
            )
        except APIKey.DoesNotExist:
            raise drf_exc.AuthenticationFailed("Invalid API key.")

        ip = _client_ip(request)
        if not key.is_active:
            raise drf_exc.AuthenticationFailed("API key is revoked or expired.")
        if not key.ip_allowed(ip):
            raise drf_exc.AuthenticationFailed("API key not allowed from this IP.")

        # Touch last_used sparingly (write at most once/minute).
        if not key.last_used_at or (timezone.now() - key.last_used_at).total_seconds() > 60:
            APIKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now(), last_used_ip=ip or None)

        # Set on the underlying HttpRequest so middleware/logging see it too.
        http_request = getattr(request, "_request", request)
        http_request.api_key = key
        http_request.organization = key.organization
        # request.user is whoever the authenticator returns; API keys act as
        # the creating user when present (lets role checks keep working).
        user = key.created_by or _OrgServiceAccount(key.organization)
        return (user, key)

    def _extract(self, request) -> str:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer ") and header[7:].startswith(self.keyword_prefix):
            return header[7:]
        api_key_header = request.headers.get("X-API-Key", "")
        return api_key_header or ""

    def authenticate_header(self, request):
        return 'Bearer realm="api"'


class _OrgServiceAccount:
    """Lightweight stand-in user for org-level keys without a creator."""

    is_authenticated = True
    is_active = True
    is_staff = False
    is_superuser = False
    pk = None
    id = None
    email = "api-key@service.fomobot"

    def __init__(self, organization):
        self.organization = organization

    def __str__(self):
        return self.email
