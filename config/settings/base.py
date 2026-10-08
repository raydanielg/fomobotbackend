from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, []),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "channels",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.billing",
    "apps.bots",
    "apps.whatsapp",
    "apps.api_keys",
    "apps.contacts",
    "apps.conversations",
    "apps.messaging",
    "apps.webhooks",
    "apps.automations",
    "apps.templates",
    "apps.logs",
    "apps.notifications",
    "apps.audit",
    "apps.dashboard",
    "apps.health",
    "apps.admin_control",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "apps.common.middleware.RequestLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://localhost:5432/fomobot",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

# Cache (Redis)
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# Auth
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.api_keys.authentication.APIKeyAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "600/minute",
        "auth": "10/minute",
        "password_reset": "5/hour",
        "send_message": "60/minute",
        "qr": "10/minute",
        "api": "300/minute",
        "webhook_test": "10/minute",
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "NON_FIELD_ERRORS_KEY": "detail",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FomoBot API",
    "DESCRIPTION": "WhatsApp Bot-as-a-Service platform API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# Email
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="FomoBot <noreply@fomobot.local>")

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 5
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.messaging.tasks.*": {"queue": "messages"},
    "apps.webhooks.tasks.*": {"queue": "webhooks"},
    "apps.whatsapp.tasks.*": {"queue": "whatsapp"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "apps.automations.tasks.*": {"queue": "automations"},
}
CELERY_BEAT_SCHEDULE = {
    "whatsapp-session-health-check": {
        "task": "apps.whatsapp.tasks.session_health_check",
        "schedule": 60.0,
    },
    "whatsapp-expired-qr-cleanup": {
        "task": "apps.whatsapp.tasks.cleanup_expired_qr",
        "schedule": 120.0,
    },
    "webhook-retry-processing": {
        "task": "apps.webhooks.tasks.process_webhook_retries",
        "schedule": 30.0,
    },
    "log-retention-cleanup": {
        "task": "apps.logs.tasks.enforce_log_retention",
        "schedule": 60.0 * 60.0,
    },
    "usage-counters-reset": {
        "task": "apps.billing.tasks.reset_usage_counters",
        "schedule": 60.0 * 60.0 * 24.0,
    },
}

# Security helpers
ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="")  # Fernet key, required in prod

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = [
    *default_headers,
    "x-organization-id",
    "x-api-key",
    "idempotency-key",
]
CORS_EXPOSE_HEADERS = ["x-request-id"]

# FomoBot platform settings
FOMOBOT = {
    "FRONTEND_URL": env("FRONTEND_URL", default="http://localhost:3000"),
    "QR_TTL_SECONDS": env.int("QR_TTL_SECONDS", default=60),
    "QR_MAX_REGENERATE_PER_HOUR": env.int("QR_MAX_REGENERATE_PER_HOUR", default=20),
    "SESSION_CONNECT_TIMEOUT_SECONDS": env.int("SESSION_CONNECT_TIMEOUT", default=300),
    "SESSION_MAX_RECONNECT_ATTEMPTS": env.int("SESSION_MAX_RECONNECT_ATTEMPTS", default=10),
    "WEBHOOK_TIMEOUT_SECONDS": env.int("WEBHOOK_TIMEOUT_SECONDS", default=10),
    "WEBHOOK_MAX_ATTEMPTS": env.int("WEBHOOK_MAX_ATTEMPTS", default=8),
    "MESSAGE_MAX_ATTEMPTS": env.int("MESSAGE_MAX_ATTEMPTS", default=5),
    "API_KEY_PREFIX": env("API_KEY_PREFIX", default="fb"),
    "DEFAULT_ORG_NAME_SUFFIX": "'s Workspace",
    "LOG_RETENTION_DAYS": env.int("LOG_RETENTION_DAYS", default=30),
    # Dev/testing escape hatch: lets the mock provider "scan" QR codes.
    "QR_SIMULATION": env.bool("QR_SIMULATION", default=False),
}

# WhatsApp provider
WHATSAPP_PROVIDER = env("WHATSAPP_PROVIDER", default="mock")
WHATSAPP_SERVICE_URL = env("WHATSAPP_SERVICE_URL", default="http://localhost:4000")
WHATSAPP_SERVICE_TOKEN = env("WHATSAPP_SERVICE_TOKEN", default="")

SENTRY_DSN = env("SENTRY_DSN", default="")

# Internationalization / misc
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Structured logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.common.logging.JSONFormatter"},
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": env("LOG_FORMAT", default="verbose"),
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "fomobot": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
