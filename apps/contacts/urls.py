from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.contacts import views

router = DefaultRouter()
router.register("contacts", views.ContactViewSet, basename="contact")

urlpatterns = [path("", include(router.urls))]
