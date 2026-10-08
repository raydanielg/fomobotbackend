from rest_framework import status

from apps.common.views import TenantViewSet
from apps.contacts import serializers as s
from apps.contacts.models import Contact
from apps.contacts.services import ContactService


class ContactViewSet(TenantViewSet):
    serializer_class = s.ContactSerializer
    required_scope = "contacts"
    filterset_fields = ["country"]
    search_fields = ["name", "profile_name", "phone_number"]
    ordering_fields = ["created_at", "name", "last_seen_at"]

    def get_queryset(self):
        return Contact.objects.all()

    def get_serializer_class(self):
        if self.action in ("create", "partial_update", "update"):
            return s.ContactCreateSerializer
        return s.ContactSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        phone = data.pop("phone_number")
        contact, created = ContactService.get_or_create(
            organization=self.get_organization(),
            phone_number=phone,
            defaults=data,
        )
        if not created:
            contact = ContactService.update(contact, **data)
        return self.ok(
            s.ContactSerializer(contact).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def retrieve(self, request, *args, **kwargs):
        return self.ok(s.ContactSerializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        contact = self.get_object()
        serializer = self.get_serializer(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        ContactService.update(contact, **serializer.validated_data)
        return self.ok(s.ContactSerializer(contact).data)

    def destroy(self, request, *args, **kwargs):
        self.get_object().soft_delete()
        return self.ok({"detail": "Contact deleted."})
