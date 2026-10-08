from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.health.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.billing.urls")),
    path("api/v1/", include("apps.bots.urls")),
    path("api/v1/", include("apps.api_keys.urls")),
    path("api/v1/", include("apps.contacts.urls")),
    path("api/v1/", include("apps.conversations.urls")),
    path("api/v1/", include("apps.messaging.urls")),
    path("api/v1/", include("apps.whatsapp.urls")),
    path("api/v1/", include("apps.webhooks.urls")),
    path("api/v1/", include("apps.automations.urls")),
    path("api/v1/", include("apps.templates.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.logs.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/admin/", include("apps.admin_control.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
]
