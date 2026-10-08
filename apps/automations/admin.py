from django.contrib import admin

from apps.automations.models import (
    Automation,
    AutomationAction,
    AutomationCondition,
    AutomationRun,
)


class ConditionInline(admin.TabularInline):
    model = AutomationCondition
    extra = 0


class ActionInline(admin.TabularInline):
    model = AutomationAction
    extra = 0


@admin.register(Automation)
class AutomationAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "trigger_type", "status", "run_count"]
    list_filter = ["status", "trigger_type"]
    search_fields = ["name", "organization__name"]
    inlines = [ConditionInline, ActionInline]


@admin.register(AutomationRun)
class AutomationRunAdmin(admin.ModelAdmin):
    list_display = ["automation", "status", "started_at", "finished_at"]
    list_filter = ["status"]
    readonly_fields = [f.name for f in AutomationRun._meta.fields]
