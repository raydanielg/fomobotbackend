from django.contrib import admin

from apps.webhooks.models import Webhook, WebhookDelivery


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "url", "status", "consecutive_failures"]
    list_filter = ["status"]
    search_fields = ["name", "url", "organization__name"]
    # Signing secret is write-only in admin.
    exclude = ["secret"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ["id", "webhook", "event", "status", "attempt_count", "response_status", "created_at"]
    list_filter = ["status"]
    readonly_fields = [f.name for f in WebhookDelivery._meta.fields]
    date_hierarchy = "created_at"
