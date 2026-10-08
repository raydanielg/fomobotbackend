from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api_keys import views

router = DefaultRouter()
router.register("api-keys", views.APIKeyViewSet, basename="api-key")

urlpatterns = [path("", include(router.urls))]
