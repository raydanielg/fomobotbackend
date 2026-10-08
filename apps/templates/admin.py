from django.contrib import admin

from apps.templates.models import MessageTemplate


@admin.register(MessageTemplate)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "language", "status"]
    list_filter = ["status", "language"]
    search_fields = ["name", "content", "organization__name"]
