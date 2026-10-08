from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from apps.accounts.models import User
from apps.common import exceptions
from apps.common.views import TenantViewSet
from apps.conversations import serializers as s
from apps.conversations.models import Conversation
from apps.conversations.services import ConversationService
from apps.messaging.serializers import MessageSerializer
from apps.messaging.services import MessageService


class ConversationViewSet(TenantViewSet):
    serializer_class = s.ConversationSerializer
    lookup_field = "id"
    required_scope = "conversations"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["status", "bot", "assigned_user"]
    search_fields = ["contact__name", "contact__phone_number", "contact__profile_name"]
    ordering_fields = ["last_message_at", "created_at"]

    def get_queryset(self):
        return Conversation.objects.select_related(
            "contact", "bot", "assigned_user", "last_message"
        )

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=["get"])
    def messages(self, request, id=None):
        conversation = self.get_object()
        qs = conversation.messages.select_related("contact").all()
        paginator = PageNumberPagination()
        paginator.page_size = 50
        paginator.max_page_size = 200
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(MessageSerializer(page, many=True).data)

    @action(detail=True, methods=["post"], url_path="messages/send")
    def send_reply(self, request, id=None):
        conversation = self.get_object()
        serializer = s.ReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message, _ = MessageService.queue_outbound(
            bot=conversation.bot,
            to=conversation.contact.phone_number,
            text=serializer.validated_data["text"],
            idempotency_key=request.headers.get("Idempotency-Key", "")[:128],
        )
        return self.ok(
            {"message_id": message.id, "status": message.status},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, id=None):
        ConversationService.mark_read(self.get_object())
        return self.ok({"detail": "Marked read."})

    @action(detail=True, methods=["post"])
    def archive(self, request, id=None):
        ConversationService.set_status(self.get_object(), Conversation.Status.ARCHIVED)
        return self.ok({"status": "archived"})

    @action(detail=True, methods=["post"])
    def close(self, request, id=None):
        ConversationService.set_status(self.get_object(), Conversation.Status.CLOSED)
        return self.ok({"status": "closed"})

    @action(detail=True, methods=["post"])
    def reopen(self, request, id=None):
        ConversationService.set_status(self.get_object(), Conversation.Status.OPEN)
        return self.ok({"status": "open"})

    @action(detail=True, methods=["post"])
    def assign(self, request, id=None):
        conversation = self.get_object()
        serializer = s.AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data.get("user_id")
        user = None
        if user_id:
            org = self.get_organization()
            is_member = org.memberships.filter(
                user_id=user_id, status="active"
            ).exists()
            if not is_member:
                raise exceptions.Forbidden(
                    detail="User is not an active member of this organization."
                )
            user = get_object_or_404(User, pk=user_id)
        ConversationService.assign(conversation, user)
        return self.ok({"assigned_user": str(user_id) if user_id else None})

    def destroy(self, request, *args, **kwargs):
        ConversationService.set_status(self.get_object(), Conversation.Status.ARCHIVED)
        return self.ok({"detail": "Conversation archived."})
