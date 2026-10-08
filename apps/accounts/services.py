import logging
from datetime import timedelta

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import LoginActivity, User
from apps.common import exceptions
from apps.common.middleware import _client_ip

logger = logging.getLogger("fomobot.accounts")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

email_token_generator = PasswordResetTokenGenerator()


def _issue_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _record_login(user, email, result, request):
    LoginActivity.objects.create(
        user=user,
        email=email,
        result=result,
        ip_address=_client_ip(request) or None,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
    )


class AuthService:
    @staticmethod
    @transaction.atomic
    def register(*, email, password, first_name="", last_name="", organization_name=""):
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        from apps.organizations.services import OrganizationService

        if not organization_name:
            organization_name = f"{first_name or email.split('@')[0]}'s workspace"
        organization = OrganizationService.create_organization(
            owner=user, name=organization_name
        )
        AuthService.send_verification_email(user)

        if organization:
            from apps.logs.services import emit
            from apps.notifications.services import NotificationService

            NotificationService.notify(
                organization=organization,
                user=user,
                type="welcome",
                title="Welcome to FomoBot",
                body=(
                    f"Hello {first_name or email}, welcome to FomoBot. "
                    "Your account has been created successfully. "
                    "Connect your WhatsApp to start building bots and automations."
                ),
            )
            emit(
                "user.registered",
                organization=organization,
                payload={"user_id": str(user.id), "email": user.email},
            )
        return user, organization

    @staticmethod
    def login(*, email, password, request) -> tuple[User, dict]:
        email = email.lower()
        user = User.objects.filter(email=email).first()

        if user and user.is_locked:
            _record_login(user, email, LoginActivity.Result.LOCKED, request)
            raise exceptions.Unauthorized(
                detail="Account temporarily locked due to failed login attempts. Try again later."
            )

        if user is None or not user.check_password(password):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = timezone.now() + LOCKOUT_DURATION
                    user.failed_login_attempts = 0
                user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
            _record_login(user, email, LoginActivity.Result.FAILED, request)
            raise exceptions.Unauthorized(detail="Invalid credentials.")

        if not user.is_active:
            _record_login(user, email, LoginActivity.Result.FAILED, request)
            raise exceptions.Unauthorized(detail="Account is deactivated.")

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = timezone.now()
        user.last_login_ip = _client_ip(request) or None
        user.save(
            update_fields=[
                "failed_login_attempts",
                "locked_until",
                "last_login_at",
                "last_login_ip",
                "updated_at",
            ]
        )
        _record_login(user, email, LoginActivity.Result.SUCCESS, request)
        return user, _issue_tokens(user)

    @staticmethod
    def logout(*, refresh_token: str):
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception as exc:
            raise exceptions.Unauthorized(detail="Invalid refresh token.") from exc

    @staticmethod
    def send_verification_email(user: User):
        uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
        token = email_token_generator.make_token(user)
        from apps.notifications.services import NotificationService

        NotificationService.send_email(
            to=user.email,
            subject="Verify your FomoBot email",
            body=(
                f"Welcome to FomoBot.\n\nVerify your email:\n"
                f"{_frontend_url()}/verify-email?uid={uid}&token={token}\n"
            ),
        )

    @staticmethod
    def verify_email(*, uid, token) -> User:
        user = _user_from_uid(uid)
        if user is None or not email_token_generator.check_token(user, token):
            raise exceptions.APIError(detail="Invalid or expired verification link.")
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified", "updated_at"])
        return user

    @staticmethod
    def request_password_reset(*, email):
        # Always succeed silently to avoid account enumeration.
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return
        uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
        token = email_token_generator.make_token(user)
        from apps.notifications.services import NotificationService

        NotificationService.send_email(
            to=user.email,
            subject="Reset your FomoBot password",
            body=f"Reset your password:\n{_frontend_url()}/reset-password?uid={uid}&token={token}\n",
        )

    @staticmethod
    def reset_password(*, uid, token, new_password) -> User:
        user = _user_from_uid(uid)
        if user is None or not email_token_generator.check_token(user, token):
            raise exceptions.APIError(detail="Invalid or expired reset link.")
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        return user

    @staticmethod
    def change_password(*, user: User, current_password, new_password):
        if not user.check_password(current_password):
            raise exceptions.APIError(detail="Current password is incorrect.")
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])


def _user_from_uid(uid):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except Exception:  # noqa: BLE001
        return None


def _frontend_url() -> str:
    from django.conf import settings

    return settings.FOMOBOT["FRONTEND_URL"].rstrip("/")
