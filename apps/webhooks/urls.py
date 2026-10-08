from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.webhooks import views

router = DefaultRouter()
router.register("webhooks", views.WebhookViewSet, basename="webhook")
router.register("webhook-deliveries", views.DeliveryViewSet, basename="webhook-delivery")

urlpatterns = [path("", include(router.urls))]
