import logging

import redis as redis_lib
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("fomobot.health")


def _check_db() -> bool:
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


def _check_redis() -> bool:
    try:
        return bool(redis_lib.from_url(settings.REDIS_URL, socket_timeout=2).ping())
    except Exception:  # noqa: BLE001
        return False


def _check_celery() -> bool:
    try:
        from config.celery import app

        return bool(app.control.inspect(timeout=1).ping())
    except Exception:  # noqa: BLE001
        return False


def _check_whatsapp() -> bool:
    if settings.WHATSAPP_PROVIDER == "mock":
        return True
    try:
        import requests

        resp = requests.get(
            f"{settings.WHATSAPP_SERVICE_URL.rstrip('/')}/health", timeout=2
        )
        return resp.status_code < 500
    except Exception:  # noqa: BLE001
        return False


@extend_schema(exclude=True)
class LiveView(APIView):
    """Liveness — process is up."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})


@extend_schema(exclude=True)
class ReadyView(APIView):
    """Readiness — all critical dependencies reachable (503 if not)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        checks = {
            "database": _check_db(),
            "redis": _check_redis(),
            "whatsapp_provider": _check_whatsapp(),
        }
        healthy = all(checks.values())
        return Response(
            {"status": "ready" if healthy else "degraded", "checks": checks},
            status=200 if healthy else 503,
        )


@extend_schema(exclude=True)
class HealthView(APIView):
    """Aggregate health incl. Celery workers."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        checks = {
            "django": True,
            "database": _check_db(),
            "redis": _check_redis(),
            "celery": _check_celery(),
            "whatsapp_provider": _check_whatsapp(),
        }
        healthy = checks["database"] and checks["redis"]
        return Response(
            {"status": "healthy" if healthy else "degraded", "checks": checks},
            status=200 if healthy else 503,
        )
