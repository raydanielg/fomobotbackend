from django.contrib import admin

from apps.conversations.models import Conversation


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "organization", "bot", "contact", "status", "unread_count", "last_message_at"]
    list_filter = ["status"]
    search_fields = ["contact__phone_number", "contact__name", "bot__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
