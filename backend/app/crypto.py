"""Generic secret encryption at rest.

Reuses the ``RECENT_CONNECTIONS_KEY``-derived Fernet key (see
``pgdatabase/connections.py``) so integration secrets like Slack bot tokens are
never stored in plaintext. The env var must stay stable — change it and
previously encrypted secrets can no longer be decrypted.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet

_CIPHER = None


def _derive_fernet_key(secret_name: str = "RECENT_CONNECTIONS_KEY") -> bytes:
    """Read an env var, validate it is present, and return a SHA-256 / base64 key."""
    secret = os.getenv(secret_name)
    if not secret:
        raise RuntimeError(f"{secret_name} is required to encrypt secrets at rest.")
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def _cipher() -> Fernet:
    global _CIPHER
    if _CIPHER is None:
        _CIPHER = Fernet(_derive_fernet_key())
    return _CIPHER


def encrypt_secret(value: str) -> str:
    """Encrypt a plaintext secret for storage."""
    return _cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    """Decrypt a secret produced by :func:`encrypt_secret`."""
    return _cipher().decrypt(value.encode()).decode()
