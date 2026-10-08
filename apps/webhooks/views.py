from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from apps.billing.services import PlanService
from apps.common.utils import random_token
from apps.common.views import TenantViewSet
from apps.webhooks import serializers as s
from apps.webhooks.models import Webhook, WebhookDelivery


class WebhookViewSet(TenantViewSet):
    serializer_class = s.WebhookSerializer
    lookup_field = "id"
    required_scope = "webhooks"
    filterset_fields = ["status", "bot"]
    search_fields = ["name", "url"]

    def get_queryset(self):
        return Webhook.objects.select_related("bot")

    def get_serializer_class(self):
        if self.action == "create":
            return s.WebhookCreateSerializer
        return s.WebhookSerializer

    def create(self, request, *args, **kwargs):
        org = self.get_organization()
        PlanService.check_limit(
            org,
            "max_webhooks",
            Webhook.objects.filter(organization=org).count(),
            noun="webhooks",
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bot = serializer.validated_data.get("bot")
        if bot and bot.organization_id != org.id:
            from apps.common import exceptions

            raise exceptions.APIError(detail="Bot does not belong to this organization.")
        webhook = serializer.save(
            organization=org, secret=f"whsec_{random_token(32)}"
        )
        from apps.audit.services import AuditService

        AuditService.log(
            actor=getattr(request, "user", None),
            organization=org,
            action="webhook.created",
            target=webhook,
        )
        # Secret is returned only once at creation.
        data = s.WebhookCreatedSerializer(webhook).data
        data["secret"] = webhook.secret
        return self.ok(data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return self.ok(s.WebhookSerializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        webhook = self.get_object()
        serializer = s.WebhookSerializer(webhook, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.ok(s.WebhookSerializer(webhook).data)

    def destroy(self, request, *args, **kwargs):
        webhook = self.get_object()
        webhook.soft_delete()
        from apps.audit.services import AuditService

        AuditService.log(
            actor=getattr(request, "user", None),
            organization=webhook.organization,
            action="webhook.deleted",
            target=webhook,
        )
        return self.ok({"detail": "Webhook deleted."})

    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request, id=None):
        webhook = self.get_object()
        webhook.secret = f"whsec_{random_token(32)}"
        webhook.save(update_fields=["secret", "updated_at"])
        return self.ok({"secret": webhook.secret})

    @action(detail=True, methods=["get"])
    def deliveries(self, request, id=None):
        webhook = self.get_object()
        qs = webhook.deliveries.all()
        paginator = PageNumberPagination()
        paginator.page_size = 25
        paginator.request = request
        page = paginator.paginate_queryset(qs, request, view=self)
        data = s.WebhookDeliverySerializer(page, many=True).data
        return self.ok(
            {
                "results": data,
                "count": paginator.page.paginator.count,
                "page": paginator.page.number,
            }
        )

    @action(detail=True, methods=["post"])
    def test(self, request, id=None):
        """Queue a synthetic test event to this webhook (bypasses subscriptions)."""
        webhook = self.get_object()
        from apps.logs.models import Event
        from apps.webhooks.tasks import deliver_webhook

        event = Event.objects.create(
            organization=webhook.organization,
            bot=webhook.bot,
            event_type="webhook.test",
            payload={"webhook_id": webhook.id, "test": True},
        )
        delivery = WebhookDelivery.objects.create(webhook=webhook, event=event)
        deliver_webhook.delay(delivery.id)
        return self.ok(
            {"detail": "Test event queued.", "delivery_id": delivery.id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="deliveries/(?P<delivery_id>[^/.]+)/replay")
    def replay_delivery(self, request, id=None, delivery_id=None):
        webhook = self.get_object()
        delivery = get_object_or_404(webhook.deliveries, pk=delivery_id)
        delivery.status = WebhookDelivery.Status.PENDING
        delivery.next_retry_at = timezone.now()
        delivery.save(update_fields=["status", "next_retry_at"])
        from apps.webhooks.tasks import deliver_webhook

        deliver_webhook.delay(delivery.id)
        return self.ok({"detail": "Delivery re-queued."})


class DeliveryViewSet(TenantViewSet):
    serializer_class = s.WebhookDeliverySerializer
    lookup_field = "id"
    required_scope = "webhooks"
    tenant_field = "webhook__organization"
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["status", "webhook"]

    def get_queryset(self):
        return WebhookDelivery.objects.select_related("webhook", "event")

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)
