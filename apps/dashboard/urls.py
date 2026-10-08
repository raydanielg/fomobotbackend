from django.urls import path

from apps.dashboard import views

urlpatterns = [
    path("dashboard/overview/", views.OverviewView.as_view(), name="dashboard-overview"),
    path(
        "dashboard/message-stats/",
        views.MessageStatsView.as_view(),
        name="dashboard-message-stats",
    ),
]
