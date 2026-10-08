from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """Abstract base: prefixed string PK + timestamps.

    Each concrete model sets ``id_prefix`` and the PK is generated as
    ``<prefix>_<32 hex chars>`` (e.g. ``bot_9f2e…``). IDs are unguessable and
    non-sequential, so they are safe to expose publicly.
    """

    id_prefix: str = "obj"

    id = models.CharField(max_length=64, primary_key=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.id:
            from apps.common.utils import new_id

            self.id = new_id(self.id_prefix)
        super().save(*args, **kwargs)


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteModel(BaseModel):
    """Base model with soft-delete support.

    ``objects`` only returns live rows; ``all_objects`` returns everything.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])
