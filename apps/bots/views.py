from django.conf import settings
from rest_framework import status
from rest_framework.decorators import action

from apps.bots import serializers as s
from apps.bots.models import Bot
from apps.bots.services import BotService
from apps.common import exceptions
from apps.common.throttles import QRCodeThrottle
from apps.common.views import TenantViewSet
from apps.whatsapp.services import WhatsAppSessionManager


class BotViewSet(TenantViewSet):
    serializer_class = s.BotSerializer
    lookup_field = "id"
    required_scope = "bots"
    filterset_fields = ["status", "connection_status"]
    search_fields = ["name", "phone_number", "slug"]
    ordering_fields = ["created_at", "name"]

    def get_queryset(self):
        return Bot.objects.select_related("organization")

    def get_serializer_class(self):
        if self.action == "create":
            return s.BotCreateSerializer
        return s.BotSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bot = BotService.create_bot(
            organization=self.get_organization(), **serializer.validated_data
        )
        return self.ok(s.BotSerializer(bot).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return self.ok(s.BotSerializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        bot = self.get_object()
        serializer = s.BotSerializer(bot, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        bot = BotService.update_bot(bot, **serializer.validated_data)
        return self.ok(s.BotSerializer(bot).data)

    def destroy(self, request, *args, **kwargs):
        bot = self.get_object()
        BotService.delete_bot(bot, actor=getattr(request, "user", None))
        return self.ok({"detail": "Bot deleted."})

    # --- Connection lifecycle ----------------------------------------
    @action(detail=True, methods=["post"])
    def connect(self, request, id=None):
        bot = self.get_object()
        session = BotService.connect(bot)
        return self.ok(self._qr_payload(bot, session))

    @action(detail=True, methods=["post"])
    def disconnect(self, request, id=None):
        session = BotService.disconnect(self.get_object())
        return self.ok({"state": session.state})

    @action(detail=True, methods=["post"], url_path="logout")
    def logout(self, request, id=None):
        session = WhatsAppSessionManager.logout(self.get_object())
        return self.ok({"state": session.state})

    @action(detail=True, methods=["post"])
    def reconnect(self, request, id=None):
        session = BotService.reconnect(self.get_object())
        return self.ok({"state": session.state})

    @action(detail=True, methods=["get"])
    def status(self, request, id=None):
        return self.ok(WhatsAppSessionManager.get_status(self.get_object()))

    @action(detail=True, methods=["get"], throttle_classes=[QRCodeThrottle])
    def qr(self, request, id=None):
        bot = self.get_object()
        session = WhatsAppSessionManager.ensure_session(bot)
        if session.qr_is_fresh:
            return self.ok(self._qr_payload(bot, session))
        # Expired or missing QR → regenerate (rate-guarded inside service).
        session = WhatsAppSessionManager.request_qr(bot)
        return self.ok(self._qr_payload(bot, session))

    @action(detail=True, methods=["post"], url_path="qr/simulate-scan")
    def simulate_scan(self, request, id=None):
        """Dev/test only: simulate the user scanning the QR in WhatsApp."""
        if settings.WHATSAPP_PROVIDER != "mock" or not settings.FOMOBOT["QR_SIMULATION"]:
            raise exceptions.Forbidden(
                detail="QR simulation requires the mock provider and QR_SIMULATION=true."
            )
        bot = self.get_object()
        session = WhatsAppSessionManager.ensure_session(bot)
        if session.state != session.State.QR_REQUIRED:
            raise exceptions.APIError(detail="No QR code is pending a scan.")
        from apps.whatsapp.providers import get_provider

        get_provider("mock").simulate_scan(
            session, phone_number=request.data.get("phone_number", "")
        )
        session.refresh_from_db()
        WhatsAppSessionManager.confirm_authenticated(
            bot,
            phone_number=(session.metadata or {}).get("mock", {}).get("phone_number", ""),
        )
        return self.ok({"state": "connected"})

    @staticmethod
    def _qr_payload(bot, session) -> dict:
        return {
            "state": session.state,
            "qr": session.qr_code,
            "expires_at": session.qr_expires_at,
        }
