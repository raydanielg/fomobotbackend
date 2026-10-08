import logging
import time

from apps.common.utils import new_request_id

logger = logging.getLogger("fomobot.request")


class RequestIDMiddleware:
    """Attach a unique request ID (``req_...``) to every request/response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-ID") or new_request_id()
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class RequestLogMiddleware:
    """Structured access log for every request (no sensitive payloads)."""

    SKIP_PREFIXES = ("/static", "/media", "/health/live")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        if request.path.startswith(self.SKIP_PREFIXES):
            return response
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "request",
            extra={
                "request_id": getattr(request, "request_id", ""),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "ip": _client_ip(request),
                "user_id": str(getattr(request.user, "id", "")) or "",
            },
        )
        self._audit_api_request(request, response, duration_ms)
        return response

    @staticmethod
    def _audit_api_request(request, response, duration_ms):
        """Persist a log row for developer (API-key) requests. Best-effort."""
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return
        try:
            import contextlib

            from apps.logs.models import ApiRequestLog

            error_code = ""
            with contextlib.suppress(AttributeError):
                error_code = (response.data or {}).get("error", {}).get("code", "")
            ApiRequestLog.objects.create(
                request_id=getattr(request, "request_id", ""),
                organization=api_key.organization,
                api_key=api_key,
                endpoint=request.path[:256],
                method=request.method,
                status_code=response.status_code,
                ip_address=_client_ip(request) or None,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
                response_ms=duration_ms,
                error_code=error_code,
            )
        except Exception:
            logger.exception("api_request_log_failed")


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
