"""Provider registry — resolve the configured WhatsApp provider."""
import functools

from django.conf import settings

from apps.whatsapp.providers.base import WhatsAppProvider

_REGISTRY = {
    "mock": "apps.whatsapp.providers.mock.MockProvider",
    "external": "apps.whatsapp.providers.external.ExternalHTTPProvider",
}


@functools.lru_cache(maxsize=8)
def get_provider(name: str | None = None) -> WhatsAppProvider:
    import importlib

    name = name or settings.WHATSAPP_PROVIDER
    path = _REGISTRY.get(name)
    if path is None:
        # Allow dotted-path custom providers, e.g. "myapp.providers.Acme".
        path = name
    module_path, _, cls_name = path.rpartition(".")
    module = importlib.import_module(module_path)
    provider = getattr(module, cls_name)()
    return provider


def register(name: str, dotted_path: str) -> None:
    _REGISTRY[name] = dotted_path
    get_provider.cache_clear()
