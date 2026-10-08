from rest_framework import serializers

from apps.automations.models import (
    Automation,
    AutomationAction,
    AutomationCondition,
    AutomationRun,
)


class ConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationCondition
        fields = ["id", "field", "operator", "value", "case_insensitive"]
        read_only_fields = ["id"]


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationAction
        fields = ["id", "action_type", "config", "order"]
        read_only_fields = ["id"]


class AutomationSerializer(serializers.ModelSerializer):
    conditions = ConditionSerializer(many=True, required=False)
    actions = ActionSerializer(many=True, required=False)

    class Meta:
        model = Automation
        fields = [
            "id",
            "name",
            "description",
            "bot",
            "trigger_type",
            "status",
            "priority",
            "run_count",
            "conditions",
            "actions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "run_count", "created_at", "updated_at"]

    def create(self, validated_data):
        conditions = validated_data.pop("conditions", [])
        actions = validated_data.pop("actions", [])
        automation = Automation.objects.create(**validated_data)
        self._sync_children(automation, conditions, actions)
        return automation

    def update(self, instance, validated_data):
        conditions = validated_data.pop("conditions", None)
        actions = validated_data.pop("actions", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if conditions is not None or actions is not None:
            self._sync_children(instance, conditions or [], actions or [])
        return instance

    @staticmethod
    def _sync_children(automation, conditions, actions):
        if conditions:
            automation.conditions.all().delete()
            for c in conditions:
                AutomationCondition.objects.create(automation=automation, **c)
        if actions:
            automation.actions.all().delete()
            for a in actions:
                AutomationAction.objects.create(automation=automation, **a)


class AutomationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRun
        fields = ["id", "automation", "event", "status", "log", "started_at", "finished_at"]
