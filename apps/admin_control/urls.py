from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.admin_control import views

router = DefaultRouter()
router.register("users", views.AdminUserViewSet, basename="admin-users-mgmt")
router.register("organizations", views.AdminOrgViewSet, basename="admin-orgs")
router.register("bots", views.AdminBotViewSet, basename="admin-bots")
router.register("sessions", views.AdminSessionViewSet, basename="admin-sessions")
router.register("messages", views.AdminMessageViewSet, basename="admin-messages")
router.register("contacts", views.AdminContactViewSet, basename="admin-contacts")
router.register("conversations", views.AdminConversationViewSet, basename="admin-conversations")
router.register("automations", views.AdminAutomationViewSet, basename="admin-automations")
router.register("audit-logs", views.AdminAuditViewSet, basename="admin-audit")
router.register("login-activity", views.LoginActivityViewSet, basename="admin-login-activity")
router.register("security-events", views.SecurityEventViewSet, basename="admin-security-events")
router.register("otp", views.OTPViewSet, basename="admin-otp")
router.register("announcements", views.AnnouncementViewSet, basename="admin-announcements")
router.register("feature-flags", views.FeatureFlagViewSet, basename="admin-flags")
router.register("roles", views.AdminRoleViewSet, basename="admin-roles")
router.register("admin-users", views.AdminUserViewSet2, basename="admin-admins")
router.register("plans", views.AdminPlanViewSet, basename="admin-plans")

urlpatterns = [
    path("overview/", views.OverviewView.as_view(), name="admin-overview"),
    path("broadcast/", views.BroadcastView.as_view(), name="admin-broadcast"),
    path("health/", views.AdminHealthView.as_view(), name="admin-health"),
    path("queues/", views.QueueView.as_view(), name="admin-queues"),
    path("", include(router.urls)),
]
