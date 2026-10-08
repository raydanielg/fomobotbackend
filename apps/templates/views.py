from rest_framework import status
from rest_framework.decorators import action

from apps.common.views import TenantViewSet
from apps.templates import serializers as s
from apps.templates.models import MessageTemplate


class TemplateViewSet(TenantViewSet):
    serializer_class = s.TemplateSerializer
    lookup_field = "id"
    required_scope = "templates"
    filterset_fields = ["status", "language"]
    search_fields = ["name", "content"]

    def get_queryset(self):
        return MessageTemplate.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.save(
            organization=self.get_organization(),
            created_by=getattr(request, "user", None),
        )
        return self.ok(s.TemplateSerializer(template).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return self.ok(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        template = self.get_object()
        serializer = self.get_serializer(template, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.ok(s.TemplateSerializer(template).data)

    def destroy(self, request, *args, **kwargs):
        self.get_object().soft_delete()
        return self.ok({"detail": "Template deleted."})

    @action(detail=True, methods=["post"])
    def render(self, request, id=None):
        template = self.get_object()
        serializer = s.TemplateRenderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.ok(
            {"rendered": template.render(serializer.validated_data["variables"])}
        )
