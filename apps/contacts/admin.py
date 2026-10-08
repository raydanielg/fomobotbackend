from django.contrib import admin

from apps.contacts.models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["phone_number", "name", "organization", "last_seen_at"]
    list_filter = ["country"]
    search_fields = ["phone_number", "name", "profile_name", "organization__name"]
