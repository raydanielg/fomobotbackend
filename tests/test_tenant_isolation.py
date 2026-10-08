"""Tenant isolation: org A's resources are invisible/unreachable to org B."""
import pytest

from apps.bots.models import Bot
from apps.contacts.models import Contact

pytestmark = pytest.mark.django_db


def test_bots_list_is_scoped(auth_client, other_auth_client, bot, other_org):
    Bot.objects.create(organization=other_org, name="Foreign Bot")
    mine = auth_client.get("/api/v1/bots/").json()["data"]["results"]
    theirs = other_auth_client.get("/api/v1/bots/").json()["data"]["results"]
    assert {b["id"] for b in mine} == {bot.id}
    assert all(b["name"] == "Foreign Bot" for b in theirs)


def test_cannot_read_foreign_bot(auth_client, other_org):
    foreign = Bot.objects.create(organization=other_org, name="Foreign")
    resp = auth_client.get(f"/api/v1/bots/{foreign.id}/")
    assert resp.status_code == 404


def test_cannot_mutate_foreign_bot(auth_client, other_org):
    foreign = Bot.objects.create(organization=other_org, name="Foreign")
    resp = auth_client.patch(f"/api/v1/bots/{foreign.id}/", {"name": "Hacked"}, format="json")
    assert resp.status_code == 404
    foreign.refresh_from_db()
    assert foreign.name == "Foreign"


def test_cannot_connect_foreign_bot(auth_client, other_org):
    foreign = Bot.objects.create(organization=other_org, name="Foreign")
    resp = auth_client.post(f"/api/v1/bots/{foreign.id}/connect/")
    assert resp.status_code == 404


def test_foreign_org_header_rejected(api_client, user, org, other_org):
    """Switching X-Organization-ID to an org the user doesn't belong to fails."""
    from rest_framework_simplejwt.tokens import RefreshToken

    token = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_ORGANIZATION_ID=other_org.id
    )
    resp = api_client.get("/api/v1/bots/")
    assert resp.status_code == 403


def test_foreign_contacts_hidden(auth_client, other_org):
    Contact.objects.create(organization=other_org, phone_number="15550101010")
    data = auth_client.get("/api/v1/contacts/").json()["data"]
    assert data["results"] == []


def test_foreign_api_key_cannot_be_used(auth_client, other_org, other_user):
    from apps.api_keys.services import APIKeyService

    _, raw = APIKeyService.create_key(
        organization=other_org, created_by=other_user,
        name="foreign", environment="test", scopes=["*"],
    )
    # Create a message in org B via its own key would work; using it must
    # scope everything to org B (never org A).
    from rest_framework.test import APIClient

    foreign_client = APIClient()
    foreign_client.credentials(HTTP_X_API_KEY=raw)
    foreign_bot = Bot.objects.create(organization=other_org, name="FB")
    resp = foreign_client.get("/api/v1/bots/")
    ids = [b["id"] for b in resp.json()["data"]["results"]]
    assert foreign_bot.id in ids

    # And the foreign key must not see org A's bot:
    mine = Bot.objects.filter(organization__name="Acme Org").first()
    if mine:
        assert mine.id not in ids


def test_api_key_auth_does_not_leak_other_org(api_key_client, org, other_org, bot):
    Bot.objects.create(organization=other_org, name="Nope")
    resp = api_key_client.get("/api/v1/bots/")
    ids = [b["id"] for b in resp.json()["data"]["results"]]
    assert ids == [bot.id]
