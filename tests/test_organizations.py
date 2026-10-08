from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_org_created_on_register(api_client):
    api_client.post(
        "/api/v1/auth/register/",
        {"email": "o@x.com", "password": "Str0ng!Pass", "organization_name": "Acme"},
        format="json",
    )
    org = Organization.objects.get(name="Acme")
    assert org.slug == "acme"
    assert org.plan.code == "free"
    m = org.memberships.get()
    assert m.role == "owner" and m.user.email == "o@x.com"


def test_list_my_orgs(auth_client, org, other_org):
    resp = auth_client.get("/api/v1/organizations/")
    ids = [o["id"] for o in resp.json()["data"]["results"]]
    assert org.id in ids and other_org.id not in ids


def test_invite_and_accept(auth_client, org):
    target = User.objects.create_user(email="new@x.com", password=PASSWORD)
    resp = auth_client.post(
        f"/api/v1/organizations/{org.id}/members/invite/",
        {"email": "new@x.com", "role": "agent"},
        format="json",
    )
    assert resp.status_code == 201
    invite = OrganizationInvitation.objects.get(organization=org, email="new@x.com")

    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(target).access_token}")
    resp = client.post("/api/v1/invitations/accept/", {"token": invite.token}, format="json")
    assert resp.status_code == 201
    assert org.memberships.get(user=target).role == "agent"


def test_wrong_email_cannot_accept(org, user):
    invite = OrganizationInvitation.objects.create(
        organization=org,
        email="someone@x.com",
        role="agent",
        token="tok123",
        expires_at=timezone.now() + timedelta(days=7),
    )
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    other = User.objects.create_user(email="evil@x.com", password=PASSWORD)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
    resp = client.post("/api/v1/invitations/accept/", {"token": invite.token}, format="json")
    assert resp.status_code in (400, 403)


def test_last_owner_cannot_leave(auth_client, org, user):
    resp = auth_client.post(f"/api/v1/organizations/{org.id}/leave/")
    assert resp.status_code == 400


def test_member_limit(org, user):
    from apps.common.exceptions import PlanLimitReached

    # FREE max_members = 3 → 2 more allowed
    u1 = User.objects.create_user(email="a1@x.com", password=PASSWORD)
    u2 = User.objects.create_user(email="a2@x.com", password=PASSWORD)
    OrganizationMembership.objects.create(organization=org, user=u1, role="agent")
    OrganizationMembership.objects.create(organization=org, user=u2, role="agent")
    with pytest.raises(PlanLimitReached):
        from apps.organizations.services import OrganizationService

        OrganizationService.invite_member(
            organization=org, email="a3@x.com", role="agent", invited_by=user
        )
