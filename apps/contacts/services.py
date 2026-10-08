import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.billing.services import PlanService
from apps.common.utils import normalize_phone
from apps.contacts.models import Contact
from apps.logs.services import emit

logger = logging.getLogger("fomobot.contacts")


class ContactService:
    @staticmethod
    def normalize(raw: str) -> str:
        try:
            return normalize_phone(raw)
        except ValueError as exc:
            from apps.common import exceptions

            raise exceptions.APIError(detail=str(exc)) from exc

    @staticmethod
    @transaction.atomic
    def get_or_create(*, organization, phone_number: str, defaults: dict | None = None) -> tuple[Contact, bool]:
        phone = ContactService.normalize(phone_number)
        contact = Contact.objects.filter(
            organization=organization, phone_number=phone
        ).first()
        if contact:
            changed = False
            for key, value in (defaults or {}).items():
                if value and not getattr(contact, key):
                    setattr(contact, key, value)
                    changed = True
            if changed:
                contact.save()
            return contact, False

        PlanService.check_limit(
            organization,
            "max_contacts",
            Contact.objects.filter(organization=organization).count(),
            noun="contacts",
        )
        try:
            contact = Contact.objects.create(
                organization=organization,
                phone_number=phone,
                last_seen_at=timezone.now(),
                **(defaults or {}),
            )
        except IntegrityError:
            contact = Contact.objects.get(organization=organization, phone_number=phone)
            return contact, False
        emit(
            "contact.created",
            organization=organization,
            payload={"contact_id": contact.id, "phone_number": phone},
        )
        return contact, True

    @staticmethod
    @transaction.atomic
    def update(contact: Contact, **fields) -> Contact:
        created = False
        if "tags" in fields or "name" in fields:
            created = True  # treat as updated signal
        for k, v in fields.items():
            setattr(contact, k, v)
        contact.save()
        if created:
            emit(
                "contact.updated",
                organization=contact.organization,
                payload={"contact_id": contact.id},
            )
        return contact
