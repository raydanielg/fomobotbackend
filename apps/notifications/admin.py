from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "organization", "user", "type", "read_at", "created_at"]
    list_filter = ["type"]
    search_fields = ["title", "body"]
