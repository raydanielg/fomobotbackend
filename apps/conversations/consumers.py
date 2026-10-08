"""Realtime inbox — pushes org-scoped events to connected dashboard clients.

Connect: ws://<host>/ws/orgs/<org_id>/inbox/?token=<jwt-access-token>
"""
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger("fomobot.ws.inbox")


class InboxConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.org_id = self.scope["url_route"]["kwargs"]["org_id"]
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return
        if not await self._is_member(user, self.org_id):
            await self.close(code=4403)
            return
        self.group = f"org_{self.org_id}_inbox"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def inbox_event(self, event):
        """Handler for group_send type='inbox_event'."""
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _is_member(self, user, org_id) -> bool:
        from apps.organizations.models import OrganizationMembership

        return OrganizationMembership.objects.filter(
            organization_id=org_id,
            user=user,
            status=OrganizationMembership.Status.ACTIVE,
        ).exists()
