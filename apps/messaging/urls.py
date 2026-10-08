from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.messaging import views

router = DefaultRouter()
router.register("messages", views.MessageViewSet, basename="message")

urlpatterns = [
    path("messages/send/", views.SendMessageView.as_view(), name="message-send"),
    path("", include(router.urls)),
]
