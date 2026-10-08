from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.automations import views

router = DefaultRouter()
router.register("automations", views.AutomationViewSet, basename="automation")

urlpatterns = [path("", include(router.urls))]
