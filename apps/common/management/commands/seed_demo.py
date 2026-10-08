"""Seed a demo workspace: org, users, bot, contacts, conversation, messages,
webhook, template, automation, API key (printed once)."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.api_keys.services import APIKeyService
from apps.automations.models import Automation, AutomationAction, AutomationCondition
from apps.bots.models import Bot
from apps.common.utils import random_token
from apps.contacts.models import Contact
from apps.conversations.models import Conversation
from apps.messaging.models import Message
from apps.organizations.models import OrganizationMembership
from apps.organizations.services import OrganizationService
from apps.templates.models import MessageTemplate
from apps.webhooks.models import SUBSCRIBABLE_EVENTS, Webhook

DEMO_PASSWORD = "DemoPass123!"


class Command(BaseCommand):
    help = "Create demo data for local development (no real WhatsApp creds)."

    def handle(self, *args, **options):
        owner = self._user("owner@demo.fomobot", "Demo", "Owner")
        agent = self._user("agent@demo.fomobot", "Demo", "Agent")

        org = owner.owned_organizations.filter(name="Demo Org").first()
        if org is None:
            org = OrganizationService.create_organization(
                owner=owner, name="Demo Org"
            )
        OrganizationMembership.objects.get_or_create(
            organization=org,
            user=agent,
            defaults={"role": OrganizationMembership.Role.AGENT},
        )

        bot, _ = Bot.objects.get_or_create(
            organization=org, slug="demo-bot", defaults={"name": "Demo Bot"}
        )

        contacts = []
        for i, (phone, name) in enumerate(
            [("1555000111", "Alice Wachira"), ("1555000222", "Brian Otieno"), ("1555000333", "Cynthia Mrema")]
        ):
            contact, _ = Contact.objects.get_or_create(
                organization=org,
                phone_number=phone,
                defaults={"name": name, "profile_name": name},
            )
            contacts.append(contact)

        conv, _ = Conversation.objects.get_or_create(
            organization=org, bot=bot, contact=contacts[0]
        )
        now = timezone.now()
        for j, (direction, text) in enumerate(
            [
                ("inbound", "Hi! Do you ship to Nairobi?"),
                ("outbound", "Yes, we deliver within 24h."),
                ("inbound", "Great — how much is shipping?"),
            ]
        ):
            msg = Message.objects.create(
                organization=org,
                bot=bot,
                conversation=conv,
                contact=contacts[0],
                direction=direction,
                message_type="text",
                text=text,
                status="delivered" if direction == "inbound" else "read",
                sent_at=now,
            )
            conv.last_message = msg
        conv.last_message_at = now
        conv.unread_count = 1
        conv.save()

        MessageTemplate.objects.get_or_create(
            organization=org,
            name="welcome",
            defaults={
                "content": "Hi {{name}}, welcome aboard! Reply STOP to opt out.",
                "status": "active",
            },
        )

        automation, created = Automation.objects.get_or_create(
            organization=org,
            name="Price auto-reply",
            defaults={
                "trigger_type": Automation.Trigger.MESSAGE_RECEIVED,
                "status": Automation.Status.ACTIVE,
                "bot": bot,
            },
        )
        if created:
            AutomationCondition.objects.create(
                automation=automation,
                field="text",
                operator="contains",
                value="price",
            )
            AutomationAction.objects.create(
                automation=automation,
                action_type=AutomationAction.Type.SEND_MESSAGE,
                config={"text": "Our pricing: https://example.com/pricing"},
            )

        webhook, _ = Webhook.objects.get_or_create(
            organization=org,
            url="https://webhook.site/fomobot-demo",
            defaults={
                "name": "Demo webhook",
                "secret": f"whsec_{random_token(32)}",
                "subscribed_events": SUBSCRIBABLE_EVENTS,
            },
        )

        _key, raw = APIKeyService.create_key(
            organization=org,
            created_by=owner,
            name="Demo key",
            environment="test",
            scopes=["*"],
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write(f"  Org:        {org.name} ({org.id})")
        self.stdout.write(f"  Login:      owner@demo.fomobot / {DEMO_PASSWORD}")
        self.stdout.write(f"  API key:    {raw}   (shown once — store it)")
        self.stdout.write(f"  Bot:        {bot.id}")
        self.stdout.write(f"  Webhook:    {webhook.id}")

    def _user(self, email, first, last):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email, password=DEMO_PASSWORD, first_name=first, last_name=last,
                is_email_verified=True,
            )
        return user
