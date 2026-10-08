from django.apps import AppConfig


class APIKeysConfig(AppConfig):
    name = "apps.api_keys"
    label = "api_keys"

    def ready(self):
        import apps.api_keys.schema  # noqa: F401 — registers OpenAPI scheme
