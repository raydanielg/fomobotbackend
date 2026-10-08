from rest_framework import generics, status
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts import serializers as s
from apps.accounts.models import LoginActivity
from apps.accounts.services import AuthService
from apps.common import responses
from apps.common.throttles import AuthRateThrottle, PasswordResetThrottle


class RegisterView(generics.GenericAPIView):
    serializer_class = s.RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = s.RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, organization = AuthService.register(**serializer.validated_data)
        return responses.success(
            {
                "user": s.UserSerializer(user).data,
                "organization": {"id": organization.id, "name": organization.name}
                if organization
                else None,
            },
            status=status.HTTP_201_CREATED,
            request=request,
        )


class LoginView(generics.GenericAPIView):
    serializer_class = s.LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = s.LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = AuthService.login(request=request, **serializer.validated_data)
        return responses.success(
            {"user": s.UserSerializer(user).data, "tokens": tokens}, request=request
        )


class RefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return responses.success({"tokens": response.data}, request=request)


class LogoutView(generics.GenericAPIView):
    class _LogoutSerializer(drf_serializers.Serializer):
        refresh = drf_serializers.CharField()

    serializer_class = _LogoutSerializer
    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            from apps.common import exceptions

            raise exceptions.APIError(detail="refresh token is required.")
        AuthService.logout(refresh_token=refresh)
        return responses.success({"detail": "Logged out."}, request=request)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = s.UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return s.UpdateProfileSerializer
        return s.UserSerializer

    def retrieve(self, request, *args, **kwargs):
        return responses.success(s.UserSerializer(self.get_object()).data, request=request)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return responses.success(s.UserSerializer(self.get_object()).data, request=request)


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = s.ChangePasswordSerializer
    def post(self, request):
        serializer = s.ChangePasswordSerializer(
            data=request.data, context={"user": request.user}
        )
        serializer.is_valid(raise_exception=True)
        AuthService.change_password(user=request.user, **serializer.validated_data)
        return responses.success({"detail": "Password changed."}, request=request)


class VerifyEmailView(generics.GenericAPIView):
    serializer_class = s.VerifyEmailSerializer
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = s.VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AuthService.verify_email(**serializer.validated_data)
        return responses.success(
            {"detail": "Email verified.", "user": s.UserSerializer(user).data},
            request=request,
        )


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = s.PasswordResetRequestSerializer
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = s.PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.request_password_reset(**serializer.validated_data)
        return responses.success(
            {"detail": "If the account exists, a reset link was sent."}, request=request
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = s.PasswordResetConfirmSerializer
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = s.PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.reset_password(**serializer.validated_data)
        return responses.success({"detail": "Password reset."}, request=request)


class LoginActivityView(generics.GenericAPIView):
    serializer_class = drf_serializers.Serializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = LoginActivity.objects.filter(user=request.user)[:50]
        data = [
            {
                "result": a.result,
                "ip_address": a.ip_address,
                "user_agent": a.user_agent,
                "created_at": a.created_at,
            }
            for a in qs
        ]
        return responses.success(data, request=request)


class DeactivateAccountView(generics.GenericAPIView):
    serializer_class = drf_serializers.Serializer
    def post(self, request):
        request.user.is_active = False
        request.user.save(update_fields=["is_active", "updated_at"])
        return responses.success({"detail": "Account deactivated."}, request=request)
