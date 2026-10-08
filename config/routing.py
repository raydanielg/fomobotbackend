from django.urls import re_path

from apps.conversations.consumers import InboxConsumer

websocket_urlpatterns = [
    re_path(r"^ws/orgs/(?P<org_id>[\w-]+)/inbox/$", InboxConsumer.as_asgi()),
]
