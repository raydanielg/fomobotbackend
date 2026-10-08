from django.urls import path

from apps.dashboard import views

urlpatterns = [
    path("dashboard/overview/", views.OverviewView.as_view(), name="dashboard-overview"),
    path(
        "dashboard/message-stats/",
        views.MessageStatsView.as_view(),
        name="dashboard-message-stats",
    ),
    path(
        "dashboard/bot-stats/",
        views.BotStatsView.as_view(),
        name="dashboard-bot-stats",
    ),
    path(
        "dashboard/status-breakdown/",
        views.StatusBreakdownView.as_view(),
        name="dashboard-status-breakdown",
    ),
    path(
        "dashboard/hourly-activity/",
        views.HourlyActivityView.as_view(),
        name="dashboard-hourly-activity",
    ),
]
