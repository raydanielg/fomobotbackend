from django.urls import path

from apps.health import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("health/live/", views.LiveView.as_view(), name="health-live"),
    path("health/ready/", views.ReadyView.as_view(), name="health-ready"),
]
