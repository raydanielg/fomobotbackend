from .development import *

# Isolation + speed for tests
DATABASES["default"]["NAME"] = "fomobot_test"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Huge throttle ceilings — rate-limit behavior is tested explicitly where needed.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/minute",
    "user": "10000/minute",
    "auth": "10000/minute",
    "password_reset": "10000/minute",
    "send_message": "10000/minute",
    "qr": "10000/minute",
    "api": "10000/minute",
    "webhook_test": "10000/minute",
}

# In-memory channel layer — no Redis dependency for ws tests.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Fixed test-only Fernet key (Django forces DEBUG=False under test).
ENCRYPTION_KEY = "itAnpo_JHRt1PfMnsk1H3wVjNalYH7CYx4XsRzzlzXo="

# Allow QR-scan simulation with the mock provider during tests.
FOMOBOT["QR_SIMULATION"] = True
