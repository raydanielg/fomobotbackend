import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.services import OrganizationService

PASSWORD = "TestPass123!"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="alice@example.com", password=PASSWORD, is_email_verified=True
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="bob@example.com", password=PASSWORD, is_email_verified=True
    )


@pytest.fixture
def org(db, user):
    return OrganizationService.create_organization(owner=user, name="Acme Org")


@pytest.fixture
def other_org(db, other_user):
    return OrganizationService.create_organization(owner=other_user, name="Other Org")


@pytest.fixture
def auth_client(api_client, user, org):
    """JWT-authenticated client scoped to `org` via header."""
    from rest_framework_simplejwt.tokens import RefreshToken

    token = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_ORGANIZATION_ID=org.id
    )
    return api_client


@pytest.fixture
def other_auth_client(api_client, other_user, other_org):
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    token = str(RefreshToken.for_user(other_user).access_token)
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_ORGANIZATION_ID=other_org.id
    )
    return client


@pytest.fixture
def bot(db, org):
    from apps.bots.models import Bot

    return Bot.objects.create(organization=org, name="Test Bot")


@pytest.fixture
def connected_bot(db, bot):
    """Bot with a fully authenticated mock WhatsApp session."""
    from apps.whatsapp.providers import get_provider
    from apps.whatsapp.services import WhatsAppSessionManager

    session = WhatsAppSessionManager.request_qr(bot)
    get_provider("mock").simulate_scan(session, phone_number="15559990000")
    WhatsAppSessionManager.confirm_authenticated(bot, phone_number="15559990000")
    bot.refresh_from_db()
    return bot


@pytest.fixture
def api_key(db, org, user):
    from apps.api_keys.services import APIKeyService

    key, raw = APIKeyService.create_key(
        organization=org,
        created_by=user,
        name="Test key",
        environment="test",
        scopes=["*"],
    )
    key.raw = raw
    return key


@pytest.fixture
def api_key_client(api_key):
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=api_key.raw)
    return client
