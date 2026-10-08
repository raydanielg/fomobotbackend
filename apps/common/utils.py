import secrets
import uuid

import phonenumbers


def new_id(prefix: str) -> str:
    """Generate a non-sequential, prefixed public ID, e.g. ``bot_a1b2c3...``."""
    return f"{prefix}_{uuid.uuid4().hex}"


def new_request_id() -> str:
    return new_id("req")


def new_event_id() -> str:
    return new_id("evt")


def random_token(length: int = 40) -> str:
    return secrets.token_urlsafe(length)[:length]


def normalize_phone(raw: str, default_region: str | None = None) -> str:
    """Normalize a phone number to digits-only E.164 form (no leading +).

    Raises ValueError if the number cannot be parsed.
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Phone number is required.")
    candidates = [raw]
    if not raw.startswith("+"):
        candidates.append(f"+{raw}")
    parsed = None
    for candidate in candidates:
        try:
            parsed = phonenumbers.parse(candidate, default_region)
            if phonenumbers.is_possible_number(parsed):
                break
            parsed = None
        except phonenumbers.NumberParseException:
            continue
    if parsed is None or not phonenumbers.is_possible_number(parsed):
        raise ValueError(f"Invalid phone number: {raw}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164).lstrip("+")


def mask_secret(secret: str, visible: int = 4) -> str:
    if not secret:
        return ""
    return f"{'*' * 8}{secret[-visible:]}"
