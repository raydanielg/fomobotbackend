
from django.utils import timezone
from rest_framework import generics, serializers

from apps.billing.models import Plan, Subscription, UsageRecord
from apps.billing.services import PlanService
from apps.common import permissions, responses
from apps.common.tenant import require_organization


class PlanListView(generics.GenericAPIView):
    serializer_class = serializers.Serializer
    queryset = Plan.objects.none()
    permission_classes = [permissions.HasOrganization]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True, is_public=True)
        data = [
            {
                "code": p.code,
                "name": p.name,
                "price_monthly": str(p.price_monthly),
                "price_yearly": str(p.price_yearly),
                "currency": p.currency,
                "limits": p.limits,
            }
            for p in plans
        ]
        return responses.success(data, request=request)


class CurrentSubscriptionView(generics.GenericAPIView):
    serializer_class = serializers.Serializer
    queryset = Subscription.objects.none()
    permission_classes = [permissions.HasOrganization]

    def get(self, request):
        org = require_organization(request)
        sub = (
            Subscription.objects.filter(organization=org)
            .select_related("plan")
            .order_by("-created_at")
            .first()
        )
        plan = PlanService.get_plan(org)
        usage = {
            r.metric: r.count
            for r in UsageRecord.objects.filter(
                organization=org, period_start=timezone.localdate()
            )
        }
        return responses.success(
            {
                "plan": {"code": plan.code, "name": plan.name, "limits": plan.limits},
                "subscription": {
                    "id": sub.id,
                    "status": sub.status,
                    "current_period_start": sub.current_period_start,
                    "current_period_end": sub.current_period_end,
                }
                if sub
                else None,
                "usage_today": usage,
            },
            request=request,
        )
