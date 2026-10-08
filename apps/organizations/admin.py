from django.contrib import admin

from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


class MembershipInline(admin.TabularInline):
    model = OrganizationMembership
    extra = 0
    readonly_fields = ["joined_at", "invited_at"]
    autocomplete_fields = ["user"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "status", "plan", "created_at"]
    list_filter = ["status", "plan"]
    search_fields = ["name", "slug", "owner__email"]
    inlines = [MembershipInline]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(OrganizationInvitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "status", "expires_at"]
    list_filter = ["status"]
    search_fields = ["email", "organization__name"]
    readonly_fields = ["token"]
