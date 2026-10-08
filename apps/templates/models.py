import re

from django.conf import settings
from django.db import models

from apps.common.models import SoftDeleteModel

VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class MessageTemplate(SoftDeleteModel):
    id_prefix = "tpl"

    class Status(models.TextChoices):
        DRAFT = "draft"
        ACTIVE = "active"
        ARCHIVED = "archived"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="templates"
    )
    name = models.CharField(max_length=120)
    content = models.TextField(help_text="Body text; use {{variable}} placeholders.")
    language = models.CharField(max_length=8, default="en")
    variables = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_template_org_name_alive",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.organization_id})"

    def extract_variables(self) -> list[str]:
        return sorted(set(VARIABLE_RE.findall(self.content)))

    def render(self, context: dict) -> str:
        def repl(match):
            return str(context.get(match.group(1), match.group(0)))

        return VARIABLE_RE.sub(repl, self.content)

    def save(self, *args, **kwargs):
        self.variables = self.extract_variables()
        super().save(*args, **kwargs)
