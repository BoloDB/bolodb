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


def get_supabase_url():
    """Return the Supabase project URL. Returns None if not configured."""
    return os.getenv("SUPABASE_URL") or None


def get_supabase_anon_key():
    """Return the Supabase anonymous key. Returns None if not configured."""
    return os.getenv("SUPABASE_ANON_KEY") or None


def get_supabase_jwt_secret():
    """Return the Supabase JWT secret for verifying tokens. Raises RuntimeError if not configured."""
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET environment variable is required for Supabase auth. "
            "Find it in your Supabase dashboard under Settings > API > JWT Secret."
        )
    return secret


def get_frontend_url():
    """Return the public frontend URL for building reset links. Returns None if not configured."""
    return os.getenv("FRONTEND_URL") or None
