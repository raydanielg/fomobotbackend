"""Tenant (organization) context resolution.

Tenant context is ALWAYS derived from authenticated credentials — never from
client-supplied IDs without a membership check:

- API-key auth  → the key's owning organization.
- JWT/session   → ``X-Organization-ID`` header validated against the user's
  memberships, falling back to their first active membership.
"""
import logging

from apps.common import exceptions

logger = logging.getLogger("fomobot.tenant")

ORG_HEADER = "HTTP_X_ORGANIZATION_ID"


def resolve_membership(request):
    """Return the active OrganizationMembership for this request, or None."""
    if getattr(request, "_membership", None) is not None:
        return request._membership

    membership = None
    api_key = getattr(request, "api_key", None)
    if api_key is not None:
        membership = _api_key_membership(api_key)
    elif request.user and request.user.is_authenticated:
        membership = _user_membership(request)

    request._membership = membership
    if membership is not None:
        request.organization = membership.organization
        request.membership = membership
    return membership


def _api_key_membership(api_key):
    from apps.organizations.models import OrganizationMembership

    # API keys act with the permissions of their creator's membership if the
    # key was created by a user; otherwise they are org-scoped service keys.
    return (
        OrganizationMembership.objects.filter(
            organization=api_key.organization,
            user=api_key.created_by,
            status=OrganizationMembership.Status.ACTIVE,
        ).first()
        or _synthetic_membership(api_key.organization)
    )


def _synthetic_membership(organization):
    """Service membership for org-level API keys whose creator left the org."""
    from apps.organizations.models import OrganizationMembership

    return OrganizationMembership(
        organization=organization,
        user=None,
        role=OrganizationMembership.Role.DEVELOPER,
        status=OrganizationMembership.Status.ACTIVE,
    )


def _user_membership(request):
    from apps.organizations.models import OrganizationMembership

    qs = OrganizationMembership.objects.select_related("organization").filter(
        user=request.user, status=OrganizationMembership.Status.ACTIVE
    )
    org_id = request.META.get(ORG_HEADER) or request.query_params.get("org") or ""
    if org_id:
        return qs.filter(organization_id=org_id).first() or qs.filter(
            organization__slug=org_id
        ).first()
    return qs.order_by("joined_at").first()


def require_organization(request):
    """Return the request's organization or raise 403."""
    membership = resolve_membership(request)
    if membership is None or getattr(request, "organization", None) is None:
        raise exceptions.Forbidden(
            detail="No active organization context. Pass X-Organization-ID or use an API key."
        )
    return request.organization
