from rest_framework.response import Response


def success(data=None, status: int = 200, request=None, **extra) -> Response:
    """Standard success envelope: {"success": true, "data": ..., "request_id": ...}."""
    body = {"success": True, "data": data if data is not None else {}}
    if extra:
        body.update(extra)
    request_id = getattr(request, "request_id", None) or _ctx_request_id()
    if request_id:
        body["request_id"] = request_id
    response = Response(body, status=status)
    if request_id:
        response["X-Request-ID"] = request_id
    return response


def _ctx_request_id() -> str:
    # Fallback for contexts without middleware (Celery, shells).
    return ""
