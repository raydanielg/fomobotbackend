from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    organization_name = serializers.CharField(
        max_length=120, required=False, allow_blank=True,
        help_text="Creates an organization owned by the new user.",
    )

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    is_platform_admin = serializers.SerializerMethodField()
    admin_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "avatar_url",
            "is_email_verified",
            "is_staff",
            "is_platform_admin",
            "admin_permissions",
            "last_login_at",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "is_email_verified", "is_staff", "last_login_at", "date_joined"]

    def get_is_platform_admin(self, u):
        if u.is_superuser or u.is_staff:
            return True
        profile = getattr(u, "admin_profile", None)
        return bool(profile and profile.status == "active")

    def get_admin_permissions(self, u):
        if u.is_superuser or u.is_staff:
            return ["*"]
        profile = getattr(u, "admin_profile", None)
        if not profile or profile.status != "active":
            return []
        perms = set()
        for role in profile.roles.all():
            perms.update(role.permissions or [])
        return sorted(perms)


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "avatar_url"]


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value, user=self.context.get("user"))
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class OTPRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=256)
    purpose = serializers.ChoiceField(
        choices=["register", "phone_verify", "login", "password_reset", "sensitive_action"]
    )
    channel = serializers.ChoiceField(choices=["email", "whatsapp", "sms"], default="email")


class OTPVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=256)
    purpose = serializers.ChoiceField(
        choices=["register", "phone_verify", "login", "password_reset", "sensitive_action"]
    )
    code = serializers.CharField(min_length=4, max_length=10)
