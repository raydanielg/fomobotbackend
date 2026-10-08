from rest_framework import serializers

from apps.contacts.models import Contact


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = [
            "id",
            "phone_number",
            "name",
            "profile_name",
            "country",
            "avatar_url",
            "tags",
            "notes",
            "metadata",
            "first_seen_at",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "first_seen_at", "created_at", "updated_at"]


class ContactCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["phone_number", "name", "country", "avatar_url", "tags", "notes", "metadata"]
