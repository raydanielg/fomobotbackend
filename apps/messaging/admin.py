from django.contrib import admin

from apps.messaging.models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "organization",
        "bot",
        "contact",
        "direction",
        "message_type",
        "status",
        "created_at",
    ]
    list_filter = ["direction", "message_type", "status"]
    search_fields = ["provider_message_id", "contact__phone_number"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"
