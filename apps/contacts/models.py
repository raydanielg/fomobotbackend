from django.db import models
from django.utils import timezone

from apps.common.models import SoftDeleteModel


class Contact(SoftDeleteModel):
    id_prefix = "ctn"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="contacts"
    )
    phone_number = models.CharField(max_length=32, db_index=True)  # digits-only E.164
    name = models.CharField(max_length=200, blank=True)
    profile_name = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=2, blank=True)
    avatar_url = models.URLField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "phone_number"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_contact_org_phone_alive",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "phone_number"]),
            models.Index(fields=["organization", "name"]),
        ]

    def __str__(self):
        return self.name or self.phone_number
