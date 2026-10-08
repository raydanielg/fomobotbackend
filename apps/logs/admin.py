from django.contrib import admin

from apps.logs.models import ApiRequestLog, Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["id", "organization", "bot", "event_type", "processing_status", "created_at"]
    list_filter = ["event_type", "processing_status"]
    search_fields = ["id"]
    date_hierarchy = "created_at"


@admin.register(ApiRequestLog)
class ApiRequestLogAdmin(admin.ModelAdmin):
    list_display = ["request_id", "organization", "endpoint", "method", "status_code", "response_ms", "created_at"]
    list_filter = ["status_code", "method"]
    search_fields = ["request_id", "endpoint"]
    readonly_fields = [f.name for f in ApiRequestLog._meta.fields]
    date_hierarchy = "created_at"
