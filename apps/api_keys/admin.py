from django.contrib import admin

from apps.api_keys.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "organization",
        "prefix",
        "environment",
        "status",
        "last_used_at",
        "expires_at",
    ]
    list_filter = ["status", "environment"]
    search_fields = ["name", "prefix", "organization__name"]
    # Never show the key hash or any secret material.
    exclude = ["hashed_key"]
    readonly_fields = ["id", "prefix", "created_at", "updated_at", "last_used_at"]
