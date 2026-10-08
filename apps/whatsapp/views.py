"""Inbound provider webhook — the WhatsApp gateway pushes events here.

Authenticated with the shared WHATSAPP_SERVICE_TOKEN (service-to-service),
NOT user credentials. Events are deduplicated via ProviderEvent before
processing, so retries are safe.
"""
import hmac
import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.common import responses

logger = logging.getLogger("fomobot.whatsapp.ingress")


@extend_schema(exclude=True)
class ProviderIngressView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.headers.get("X-FomoBot-Provider-Token", "")
        expected = settings.WHATSAPP_SERVICE_TOKEN
        if not expected or not hmac.compare_digest(token, expected):
            from rest_framework.exceptions import AuthenticationFailed

            raise AuthenticationFailed("Invalid provider token.")
        event = request.data or {}
        from apps.whatsapp.tasks import provider_webhook_dispatch

        provider_webhook_dispatch.delay(settings.WHATSAPP_PROVIDER, event)
        return responses.success(
            {"received": True}, status=status.HTTP_202_ACCEPTED, request=request
        )
