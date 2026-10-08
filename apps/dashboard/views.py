from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import generics, serializers

from apps.bots.models import Bot
from apps.common import permissions, responses
from apps.common.tenant import require_organization
from apps.contacts.models import Contact
from apps.conversations.models import Conversation
from apps.messaging.models import Message


class OverviewView(generics.GenericAPIView):
    serializer_class = serializers.Serializer
    queryset = Message.objects.none()
    """GET /api/v1/dashboard/overview/ — headline metrics for the org."""

    permission_classes = [permissions.HasOrganization, permissions.HasOrgRole]
    required_roles = ("owner", "admin", "developer", "agent", "viewer")

    def get(self, request):
        org = require_organization(request)

        bots = Bot.objects.filter(organization=org)
        messages = Message.objects.filter(organization=org)
        msg_stats = messages.aggregate(
            total=Count("id"),
            inbound=Count("id", filter=Q(direction="inbound")),
            outbound=Count("id", filter=Q(direction="outbound")),
            failed=Count("id", filter=Q(status="failed")),
            delivered=Count("id", filter=Q(status__in=["delivered", "read"])),
        )
        sent_like = msg_stats["outbound"] or 0
        data = {
            "messages": {
                **msg_stats,
                "delivery_rate": round(
                    msg_stats["delivered"] / sent_like * 100, 1
                )
                if sent_like
                else None,
            },
            "bots": {
                "total": bots.count(),
                "connected": bots.filter(connection_status="connected").count(),
            },
            "contacts": Contact.objects.filter(organization=org).count(),
            "conversations": {
                "total": Conversation.objects.filter(organization=org).count(),
                "open": Conversation.objects.filter(
                    organization=org, status="open"
                ).count(),
                "unread": sum(
                    Conversation.objects.filter(organization=org).values_list(
                        "unread_count", flat=True
                    )[:500]
                ),
            },
        }
        return responses.success(data, request=request)


class MessageStatsView(generics.GenericAPIView):
    serializer_class = serializers.Serializer
    queryset = Message.objects.none()
    """GET /api/v1/dashboard/message-stats/?days=14 — daily inbound/outbound."""

    permission_classes = [permissions.HasOrganization, permissions.HasOrgRole]

    def get(self, request):
        org = require_organization(request)
        days = min(int(request.query_params.get("days", 14)), 90)
        since = timezone.now() - timedelta(days=days)
        rows = (
            Message.objects.filter(organization=org, created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                inbound=Count("id", filter=Q(direction="inbound")),
                outbound=Count("id", filter=Q(direction="outbound")),
                failed=Count("id", filter=Q(status="failed")),
            )
            .order_by("day")
        )
        return responses.success(list(rows), request=request)
