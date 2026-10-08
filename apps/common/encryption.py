"""Encryption-at-rest helpers for sensitive values (session credentials,
webhook secrets are hashed, not encrypted — this is for data we must read back).
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("fomobot.encryption")

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            if settings.DEBUG:
                # Dev-only deterministic key — never use in production.
                key = base64.urlsafe_b64encode(
                    hashlib.sha256(b"fomobot-dev-only-key").digest()
                ).decode()
                logger.warning("ENCRYPTION_KEY not set; using dev-only derived key.")
            else:
                raise ImproperlyConfigured(
                    "ENCRYPTION_KEY must be set in production. "
                    "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_str(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_str(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def hash_secret(secret: str) -> str:
    """One-way hash for secrets we only ever need to verify (API secrets)."""
    import hmac

    salt = settings.SECRET_KEY.encode()
    return hmac.new(salt, secret.encode(), hashlib.sha256).hexdigest()
