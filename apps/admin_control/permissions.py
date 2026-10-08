from rest_framework.permissions import BasePermission

from apps.admin_control.models import AdminUser


def admin_for(user):
    """Return the active AdminUser profile, or synthesize one for staff/superusers."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser or user.is_staff:
        profile = getattr(user, "admin_profile", None)
        return profile or user  # superuser path — has_perm always True via caller
    profile = getattr(user, "admin_profile", None)
    if profile and profile.status == AdminUser.Status.ACTIVE:
        return profile
    return None


class IsPlatformAdmin(BasePermission):
    """Any active platform administrator (staff, superuser or AdminUser)."""

    def has_permission(self, request, view):
        return admin_for(request.user) is not None


class AdminPermission(BasePermission):
    """Granular permission check — view class sets `required_admin_perm`.

    Superusers and staff bypass; AdminUser profiles check their roles.
    """

    message = "You don't have permission to perform this action."

    def _perm_for(self, view) -> str:
        perm = getattr(view, "required_admin_perm", None)
        if callable(perm):
            return perm()
        if isinstance(perm, dict):
            action = getattr(view, "action", None)
            return perm.get(action, perm.get("default", ""))
        return perm or ""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or user.is_staff:
            return True
        profile = getattr(user, "admin_profile", None)
        if not profile or profile.status != AdminUser.Status.ACTIVE:
            return False
        perm = self._perm_for(view)
        if not perm:
            return True
        return profile.has_perm(perm)
