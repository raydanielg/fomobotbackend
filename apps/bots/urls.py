from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.bots import views

router = DefaultRouter()
router.register("bots", views.BotViewSet, basename="bot")

urlpatterns = [path("", include(router.urls))]
