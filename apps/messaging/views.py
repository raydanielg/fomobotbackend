from django.shortcuts import get_object_or_404
from rest_framework import generics, status

from apps.bots.models import Bot
from apps.common import permissions, responses
from apps.common.tenant import require_organization
from apps.common.throttles import SendMessageThrottle
from apps.common.views import TenantViewSet
from apps.messaging import serializers as s
from apps.messaging.models import Message
from apps.messaging.services import MessageService


class MessageViewSet(TenantViewSet):
    """List/retrieve messages. Sending goes through /messages/send/."""

    serializer_class = s.MessageSerializer
    required_scope = "messages"
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["status", "direction", "message_type", "bot", "conversation"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        return Message.objects.select_related("bot", "contact", "conversation")

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)


class SendMessageView(generics.GenericAPIView):
    """POST /api/v1/messages/send/ — async, idempotent, returns queued message."""

    permission_classes = [
        permissions.HasOrganization,
        permissions.HasOrgRole,
        permissions.HasAPIScope,
    ]
    serializer_class = s.SendMessageSerializer
    required_scope = "messages"
    throttle_classes = [SendMessageThrottle]

    def post(self, request):
        org = require_organization(request)
        serializer = s.SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        bot = get_object_or_404(Bot.objects, pk=data["bot_id"], organization=org)
        idempotency_key = request.headers.get("Idempotency-Key", "")[:128]

        message, created = MessageService.queue_outbound(
            bot=bot,
            to=data["to"],
            message_type=data["type"],
            text=data["text"],
            media_url=data["media_url"],
            caption=data["caption"],
            metadata=data["metadata"],
            idempotency_key=idempotency_key,
        )
        return responses.success(
            {
                "message_id": message.id,
                "status": message.status,
                "conversation_id": message.conversation_id,
                "idempotent_replay": not created,
            },
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
            request=request,
        )
