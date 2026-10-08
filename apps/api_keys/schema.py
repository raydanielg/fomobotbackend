"""drf-spectacular extension: document API key auth in the OpenAPI schema."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.api_keys.authentication.APIKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Developer API key, e.g. `fb_live_...` "
            "(also accepted as `Authorization: Bearer fb_...`).",
        }
