from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.templates import views

router = DefaultRouter()
router.register("templates", views.TemplateViewSet, basename="template")

urlpatterns = [path("", include(router.urls))]
