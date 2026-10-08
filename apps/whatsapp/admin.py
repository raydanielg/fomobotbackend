from django.contrib import admin

from apps.whatsapp.models import ProviderEvent, WhatsAppSession


@admin.register(WhatsAppSession)
class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = [
        "bot",
        "organization",
        "provider",
        "state",
        "last_heartbeat_at",
        "reconnect_attempts",
    ]
    list_filter = ["state", "provider"]
    search_fields = ["bot__name", "provider_session_id"]
    # Credentials are encrypted; hide the ciphertext entirely from admin.
    exclude = ["credentials_encrypted"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(ProviderEvent)
class ProviderEventAdmin(admin.ModelAdmin):
    list_display = ["provider", "event_type", "provider_event_id", "status", "created_at"]
    list_filter = ["provider", "event_type", "status"]
    readonly_fields = [f.name for f in ProviderEvent._meta.fields]
