from django.contrib import admin

from apps.bots.models import Bot


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "organization",
        "phone_number",
        "status",
        "connection_status",
        "last_connected_at",
    ]
    list_filter = ["status", "connection_status"]
    search_fields = ["name", "phone_number", "organization__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
