"""Centralized API error handling.

All errors return: {"success": false, "error": {"code": ..., "message": ...},
"request_id": ...}. Internal exceptions are never leaked to clients.
"""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("fomobot.errors")


class ErrorCodes:
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    CONFLICT = "CONFLICT"
    BOT_NOT_CONNECTED = "BOT_NOT_CONNECTED"
    WHATSAPP_ERROR = "WHATSAPP_ERROR"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    INVALID_API_KEY = "INVALID_API_KEY"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    WEBHOOK_FAILED = "WEBHOOK_FAILED"
    PLAN_LIMIT_REACHED = "PLAN_LIMIT_REACHED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class APIError(drf_exceptions.APIException):
    """Base class for application errors with a stable machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The request is invalid."
    default_code = ErrorCodes.INVALID_REQUEST
    error_code = ErrorCodes.INVALID_REQUEST

    def __init__(self, detail=None, code=None):
        super().__init__(detail=detail, code=code)
        if self.error_code == ErrorCodes.INVALID_REQUEST and code:
            self.error_code = code


class ValidationFailed(APIError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Validation failed."
    error_code = ErrorCodes.VALIDATION_ERROR


class Unauthorized(APIError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentication failed."
    error_code = ErrorCodes.UNAUTHORIZED


class Forbidden(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    error_code = ErrorCodes.FORBIDDEN


class ConflictError(APIError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource conflict."
    error_code = ErrorCodes.CONFLICT


class PlanLimitReached(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Your current plan does not allow this action."
    error_code = ErrorCodes.PLAN_LIMIT_REACHED


class BotNotConnected(APIError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The bot is not connected to WhatsApp."
    error_code = ErrorCodes.BOT_NOT_CONNECTED


class WhatsAppError(APIError):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "WhatsApp provider error."
    error_code = ErrorCodes.WHATSAPP_ERROR


class SessionExpired(APIError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "WhatsApp session expired; reconnect required."
    error_code = ErrorCodes.SESSION_EXPIRED


def _request_id(context) -> str:
    request = context.get("request")
    return getattr(request, "request_id", "") or ""


def _envelope(code: str, message: str, detail=None) -> dict:
    error = {"code": code, "message": message}
    if detail is not None and not isinstance(detail, str):
        error["details"] = detail
    return error


def api_exception_handler(exc, context):
    request_id = _request_id(context)

    if isinstance(exc, Http404):
        exc = drf_exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exceptions.PermissionDenied()

    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — never leak internals.
        logger.exception(
            "unhandled_exception",
            extra={"request_id": request_id, "path": getattr(context.get("request"), "path", "")},
            exc_info=exc,
        )
        body = {
            "success": False,
            "error": {
                "code": ErrorCodes.INTERNAL_ERROR,
                "message": "An internal error occurred.",
            },
            "request_id": request_id,
        }
        return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    code = getattr(exc, "error_code", None) or getattr(exc, "default_code", None)
    detail = response.data

    if isinstance(exc, drf_exceptions.ValidationError):
        code = ErrorCodes.VALIDATION_ERROR
        message = "Validation failed."
    elif isinstance(exc, drf_exceptions.NotAuthenticated):
        code = ErrorCodes.UNAUTHORIZED
        message = _first_msg(detail)
    elif isinstance(exc, drf_exceptions.PermissionDenied):
        code = ErrorCodes.FORBIDDEN
        message = _first_msg(detail)
    elif isinstance(exc, drf_exceptions.NotFound):
        code = ErrorCodes.NOT_FOUND
        message = "Not found."
    elif isinstance(exc, drf_exceptions.Throttled):
        code = ErrorCodes.RATE_LIMITED
        message = "Rate limit exceeded. Please retry later."
    else:
        code = (code or ErrorCodes.INVALID_REQUEST).upper()
        message = _first_msg(detail)

    response.data = {
        "success": False,
        "error": _envelope(code, message, detail if code == ErrorCodes.VALIDATION_ERROR else None),
        "request_id": request_id,
    }
    response["X-Request-ID"] = request_id
    if isinstance(exc, drf_exceptions.Throttled) and exc.wait:
        response["Retry-After"] = int(exc.wait)
    return response


def _first_msg(detail) -> str:
    if isinstance(detail, dict):
        for value in detail.values():
            return _first_msg(value)
        return "The request is invalid."
    if isinstance(detail, (list, tuple)):
        return _first_msg(detail[0]) if detail else "The request is invalid."
    return str(detail)
