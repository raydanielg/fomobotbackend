from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.organizations import views

router = DefaultRouter()
router.register("organizations", views.OrganizationViewSet, basename="organization")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "invitations/accept/",
        views.AcceptInvitationView.as_view(),
        name="invitation-accept",
    ),
]
