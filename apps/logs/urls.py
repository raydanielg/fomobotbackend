from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.logs import views

router = DefaultRouter()
router.register("logs/api-requests", views.ApiRequestLogViewSet, basename="api-request-log")
router.register("logs/events", views.EventViewSet, basename="event")

urlpatterns = [path("", include(router.urls))]
