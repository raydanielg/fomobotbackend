from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("me/activity/", views.LoginActivityView.as_view(), name="auth-activity"),
    path("me/deactivate/", views.DeactivateAccountView.as_view(), name="auth-deactivate"),
    path("password/change/", views.ChangePasswordView.as_view(), name="auth-password-change"),
    path("password/reset/", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "password/reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("verify-email/", views.VerifyEmailView.as_view(), name="auth-verify-email"),
    path("otp/request/", views.OTPRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", views.OTPVerifyView.as_view(), name="auth-otp-verify"),
]
