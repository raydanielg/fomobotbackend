from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import LoginActivity, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "full_name", "is_active", "is_email_verified", "is_staff", "last_login_at"]
    list_filter = ["is_active", "is_staff", "is_email_verified"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "avatar_url")}),
        (
            "Security",
            {
                "fields": (
                    "is_email_verified",
                    "failed_login_attempts",
                    "locked_until",
                    "totp_enabled",
                    "last_login_at",
                    "last_login_ip",
                )
            },
        ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "password1", "password2", "is_staff", "is_superuser")}),
    )


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ["email", "result", "ip_address", "created_at"]
    list_filter = ["result"]
    search_fields = ["email"]
    readonly_fields = [f.name for f in LoginActivity._meta.fields]
