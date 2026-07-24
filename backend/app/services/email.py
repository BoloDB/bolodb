"""Email sending service via Resend REST API.

Uses httpx (already a dependency) to call Resend's transactional email API.
Falls back gracefully when RESEND_API_KEY is not configured.
"""

import logging
import os

import httpx

log = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10.0


def _get_api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY")


def _get_from_email() -> str:
    return os.environ.get("RESEND_FROM_EMAIL", "noreply@bolodb.dev")


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success, False on failure."""
    api_key = _get_api_key()
    if not api_key:
        log.warning("RESEND_API_KEY not configured — skipping email send")
        return False

    payload = {
        "from": _get_from_email(),
        "to": [to],
        "subject": subject,
        "html": html,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            r = await client.post(
                RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            r.raise_for_status()
            log.info("Email sent to %s — subject: %s", to, subject)
            return True
    except (httpx.HTTPError, ValueError) as e:
        log.error("Failed to send email to %s: %s", to, e)
        return False


async def send_verification_email(to: str, code: str) -> bool:
    """Send a verification OTP email."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:system-ui,-apple-system,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a2e">
      <h2 style="margin:0 0 16px;font-size:22px;font-weight:700">Verify your email</h2>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.5;color:#555">
        Use the code below to verify your BoloDB account. This code expires in 10 minutes.
      </p>
      <div style="font-size:32px;font-weight:800;letter-spacing:0.15em;text-align:center;padding:20px;background:#f5f5f5;border-radius:12px;margin:0 0 20px;font-family:monospace">
        {code}
      </div>
      <p style="margin:0;font-size:13px;color:#999">
        If you didn't create a BoloDB account, you can safely ignore this email.
      </p>
    </body>
    </html>
    """
    return await send_email(to, "Your BoloDB verification code", html)


async def send_password_reset_email(to: str, reset_link: str) -> bool:
    """Send a password reset email."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:system-ui,-apple-system,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a2e">
      <h2 style="margin:0 0 16px;font-size:22px;font-weight:700">Reset your password</h2>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.5;color:#555">
        Click the button below to reset your BoloDB password. This link expires in 15 minutes.
      </p>
      <a href="{reset_link}" style="display:inline-block;padding:12px 28px;background:#1a1a2e;color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:600">
        Reset password
      </a>
      <p style="margin:20px 0 0;font-size:13px;color:#999">
        If you didn't request a password reset, you can safely ignore this email.
      </p>
    </body>
    </html>
    """
    return await send_email(to, "Reset your BoloDB password", html)


async def send_workspace_invite_email(
    to: str, workspace_name: str, invite_code: str
) -> bool:
    """Send a workspace invite email."""
    import html

    safe_name = html.escape(workspace_name)
    safe_code = html.escape(invite_code)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:system-ui,-apple-system,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a2e">
      <h2 style="margin:0 0 16px;font-size:22px;font-weight:700">You've been invited!</h2>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.5;color:#555">
        You have been invited to join the <strong>{safe_name}</strong> workspace on BoloDB.
      </p>
      <div style="font-size:24px;font-weight:800;letter-spacing:0.1em;text-align:center;padding:20px;background:#f5f5f5;border-radius:12px;margin:0 0 20px;font-family:monospace">
        {safe_code}
      </div>
      <p style="margin:20px 0 0;font-size:13px;color:#999">
        Copy this code and paste it into the "Join Workspace" screen to accept the invitation.
      </p>
    </body>
    </html>
    """
    return await send_email(
        to, f"Invitation to join {workspace_name} on BoloDB", html_content
    )
