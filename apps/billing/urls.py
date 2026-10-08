from django.urls import path

from apps.billing import views

urlpatterns = [
    path("plans/", views.PlanListView.as_view(), name="plan-list"),
    path("subscription/", views.CurrentSubscriptionView.as_view(), name="subscription-current"),
]
