from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    scope = "auth"


class PasswordResetThrottle(AnonRateThrottle):
    scope = "password_reset"


class SendMessageThrottle(ScopedRateThrottle):
    scope = "send_message"


class QRCodeThrottle(ScopedRateThrottle):
    scope = "qr"


class DeveloperAPIThrottle(ScopedRateThrottle):
    """Plan-aware throttle for developer API keys.

    The effective rate is read from the organization's plan limits
    (``api_requests_per_minute``), falling back to the default scope rate.
    """

    scope = "api"

    def allow_request(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is not None:
            from apps.billing.services import PlanService

            rpm = PlanService.get_limit(
                api_key.organization, "api_requests_per_minute"
            )
            if rpm:
                self.rate = f"{int(rpm)}/minute"
                self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)
