"""Organization-scoped permission classes.

Views declare ``required_roles`` (any-of) and/or ``required_scope`` (API-key
scope). Membership is resolved by ``common.tenant`` — org IDs from the client
are never trusted without a membership/API-key check.
"""
from rest_framework.permissions import BasePermission

from apps.common.tenant import resolve_membership

# Role hierarchy helpers
ALL_ROLES = ("owner", "admin", "developer", "agent", "viewer")
WRITE_ROLES = ("owner", "admin", "developer", "agent")
ADMIN_ROLES = ("owner", "admin")


class HasOrganization(BasePermission):
    """Requires a resolvable, active organization context."""

    message = "No active organization context."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated) and getattr(
            request, "api_key", None
        ) is None:
            return False
        return resolve_membership(request) is not None


class HasOrgRole(BasePermission):
    """Requires membership role ∈ view.required_roles (default: any member)."""

    message = "Insufficient organization role."

    def has_permission(self, request, view):
        membership = resolve_membership(request)
        if membership is None:
            return False
        required = getattr(view, "required_roles", None)
        if required is None:
            required = ALL_ROLES if request.method in ("GET", "HEAD", "OPTIONS") else WRITE_ROLES
        return membership.role in required


class HasAPIScope(BasePermission):
    """When authenticated via API key, enforce ``view.required_scope``.

    ``required_scope`` e.g. "messages:write". Session/JWT auth (dashboard)
    bypasses scope checks — roles govern those requests instead.
    """

    message = "API key lacks the required scope."

    def has_permission(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return True  # dashboard auth path
        scope = getattr(view, "required_scope", None)
        if not scope:
            return True
        if ":" not in scope:
            action = "read" if request.method in ("GET", "HEAD", "OPTIONS") else "write"
            scope = f"{scope}:{action}"
        return api_key.has_scope(scope)


class SameOrganizationObject(BasePermission):
    """Object-level guard: obj.organization must match request organization."""

    message = "Object does not belong to your organization."

    def has_object_permission(self, request, view, obj):
        org = getattr(request, "organization", None)
        if org is None:
            resolve_membership(request)
            org = getattr(request, "organization", None)
        if org is None:
            return False
        obj_org = getattr(obj, "organization_id", None) or getattr(
            getattr(obj, "organization", None), "id", None
        )
        return obj_org == org.id
