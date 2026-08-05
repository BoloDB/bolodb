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
    """Whether session cookies carry the Secure flag (sent over HTTPS only).

    Defaults to **on**. Forgetting to set this used to mean session cookies were
    sent in clear over HTTP — and forgetting is the common case, because nothing
    about the app misbehaves when it is wrong. The two failure modes are not
    comparable: left off in production, credentials are readable by anyone on the
    path; left on in local development, the browser drops the cookie and you find
    out immediately, at the first sign-in.

    So the default fails towards the one you notice. Plain-HTTP deployments set
    COOKIE_SECURE=false explicitly, which is a decision someone has to make on
    purpose rather than one they can drift into.
    """
    return os.getenv("COOKIE_SECURE", "true").lower() != "false"


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


def get_resend_api_key():
    """Return the Resend API key for sending emails. Returns None if not configured."""
    return os.getenv("RESEND_API_KEY") or None


def get_resend_from_email():
    """Return the sender email address for Resend. Returns a default if not configured."""
    return os.getenv("RESEND_FROM_EMAIL", "noreply@bolodb.dev")


def get_slack_client_id():
    """Return the Slack app client ID. Returns None if not configured."""
    return os.getenv("SLACK_CLIENT_ID") or None


def get_slack_client_secret():
    """Return the Slack app client secret. Returns None if not configured."""
    return os.getenv("SLACK_CLIENT_SECRET") or None


def get_slack_redirect_uri():
    """Return the Slack OAuth redirect URI (backend callback). None if not configured."""
    return os.getenv("SLACK_REDIRECT_URI") or None


def get_slack_signing_secret():
    """Return the Slack signing secret for verifying inbound events. None if not configured."""
    return os.getenv("SLACK_SIGNING_SECRET") or None
