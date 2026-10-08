from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from apps.automations import serializers as s
from apps.automations.models import Automation
from apps.billing.services import PlanService
from apps.common.views import TenantViewSet


class AutomationViewSet(TenantViewSet):
    serializer_class = s.AutomationSerializer
    lookup_field = "id"
    filterset_fields = ["status", "trigger_type", "bot"]
    search_fields = ["name"]

    def get_queryset(self):
        return Automation.objects.prefetch_related("conditions", "actions")

    def create(self, request, *args, **kwargs):
        org = self.get_organization()
        PlanService.check_limit(
            org,
            "max_automation_rules",
            Automation.objects.filter(organization=org).count(),
            noun="automation rules",
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=org)
        return self.ok(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        automation = self.get_object()
        serializer = self.get_serializer(automation, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.ok(s.AutomationSerializer(automation).data)

    def destroy(self, request, *args, **kwargs):
        self.get_object().soft_delete()
        return self.ok({"detail": "Automation deleted."})

    @action(detail=True, methods=["get"])
    def runs(self, request, id=None):
        automation = self.get_object()
        qs = automation.runs.all()
        paginator = PageNumberPagination()
        paginator.page_size = 25
        page = paginator.paginate_queryset(qs, request, view=self)
        data = s.AutomationRunSerializer(page, many=True).data
        return self.ok(
            {"results": data, "count": paginator.page.paginator.count}
        )
