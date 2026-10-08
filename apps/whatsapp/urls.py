from django.urls import path

from apps.whatsapp import views

urlpatterns = [
    path(
        "whatsapp/ingress/",
        views.ProviderIngressView.as_view(),
        name="whatsapp-ingress",
    ),
]
