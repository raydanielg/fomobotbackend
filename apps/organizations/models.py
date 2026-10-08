from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.common.models import BaseModel, SoftDeleteModel


class Organization(SoftDeleteModel):
    id_prefix = "org"

    class Status(models.TextChoices):
        ACTIVE = "active"
        SUSPENDED = "suspended"
        CLOSED = "closed"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_organizations",
    )
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="org-logos/", null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    country = models.CharField(max_length=2, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    plan = models.ForeignKey(
        "billing.Plan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organizations",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "org"
            slug, i = base, 1
            while Organization.all_objects.filter(slug=slug).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)


class OrganizationMembership(BaseModel):
    id_prefix = "mem"

    class Role(models.TextChoices):
        OWNER = "owner"
        ADMIN = "admin"
        DEVELOPER = "developer"
        AGENT = "agent"
        VIEWER = "viewer"

    class Status(models.TextChoices):
        ACTIVE = "active"
        INVITED = "invited"
        SUSPENDED = "suspended"
        REMOVED = "removed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VIEWER)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    joined_at = models.DateTimeField(default=timezone.now)
    invited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="uniq_membership_org_user",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


class OrganizationInvitation(BaseModel):
    id_prefix = "inv"

    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        REVOKED = "revoked"
        EXPIRED = "expired"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=16,
        choices=OrganizationMembership.Role.choices,
        default=OrganizationMembership.Role.AGENT,
    )
    token = models.CharField(max_length=96, unique=True, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["email", "status"])]

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()
