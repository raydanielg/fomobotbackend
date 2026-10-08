import pytest

from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_register_creates_user_and_org(api_client):
    resp = api_client.post(
        "/api/v1/auth/register/",
        {
            "email": "new@example.com",
            "password": "Str0ng!Pass",
            "organization_name": "NewCo",
        },
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["user"]["email"] == "new@example.com"
    assert body["data"]["organization"]["name"] == "NewCo"
    assert "request_id" in body


def test_register_rejects_weak_password(api_client):
    resp = api_client.post(
        "/api/v1/auth/register/",
        {"email": "weak@example.com", "password": "123"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_success(api_client, user):
    resp = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access" in data["tokens"] and "refresh" in data["tokens"]


def test_login_wrong_password_returns_401_envelope(api_client, user):
    resp = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in body


def test_failed_logins_lock_account(api_client, user):
    from apps.accounts.services import MAX_FAILED_ATTEMPTS

    for _ in range(MAX_FAILED_ATTEMPTS):
        api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "bad"},
            format="json",
        )
    user.refresh_from_db()
    assert user.locked_until is not None
    resp = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert resp.status_code == 401
    assert "locked" in resp.json()["error"]["message"].lower()


def test_me_requires_auth(api_client):
    resp = api_client.get("/api/v1/auth/me/")
    assert resp.status_code == 401


def test_me_returns_profile(auth_client, user):
    resp = auth_client.get("/api/v1/auth/me/")
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == user.email


def test_refresh_token(api_client, user):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    refresh = login.json()["data"]["tokens"]["refresh"]
    resp = api_client.post("/api/v1/auth/refresh/", {"refresh": refresh}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.json()["data"]["tokens"]


def test_logout_blacklists_refresh(api_client, user):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    refresh = login.json()["data"]["tokens"]["refresh"]
    access = login.json()["data"]["tokens"]["access"]
    client = api_client
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    resp = client.post("/api/v1/auth/logout/", {"refresh": refresh}, format="json")
    assert resp.status_code == 200
    resp = api_client.post("/api/v1/auth/refresh/", {"refresh": refresh}, format="json")
    assert resp.status_code == 401
