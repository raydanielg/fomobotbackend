from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.conversations import views

router = DefaultRouter()
router.register("conversations", views.ConversationViewSet, basename="conversation")

urlpatterns = [path("", include(router.urls))]
