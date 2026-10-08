from rest_framework import serializers

from apps.templates.models import MessageTemplate


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "name",
            "content",
            "language",
            "variables",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "variables", "created_at", "updated_at"]


class TemplateRenderSerializer(serializers.Serializer):
    variables = serializers.DictField(default=dict)
