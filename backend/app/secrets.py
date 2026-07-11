"""Centralized secret management — single source of truth for JWT and crypto keys."""

import os


def get_jwt_secret():
    """Return the JWT signing secret. Raises RuntimeError if not configured."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is required. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return secret


def get_cookie_secure():
    """Return True if cookies should use the Secure flag (HTTPS only)."""
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"
