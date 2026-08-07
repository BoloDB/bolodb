"""Email sending service via Resend REST API.

Uses httpx (already a dependency) to call Resend's transactional email API.
Falls back gracefully when RESEND_API_KEY is not configured.
"""

import base64
import logging
import os

import httpx

log = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10.0
ATTACHMENT_TIMEOUT_SECONDS = 30.0


def _get_api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY")


def _get_from_email() -> str:
    # Blank counts as unset: docker-compose substitutes an undefined variable to
    # an empty string rather than dropping it, and "from": "" is a payload Resend
    # rejects outright.
    return os.environ.get("RESEND_FROM_EMAIL", "").strip() or "noreply@bolodb.dev"


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    attachments: list[dict] | None = None,
) -> bool:
    """Send an email via Resend. Returns True on success, False on failure.

    ``to`` accepts a list for reports that go to several recipients at once.
    ``attachments`` follows Resend's shape — ``{"filename": ..., "content": ...}``
    where content is base64 — see ``attachment_from_text`` for building one.

    Attachments push a report well past the 10s that suits a verification code,
    so the timeout scales with the payload rather than being one fixed value.
    """
    api_key = _get_api_key()
    if not api_key:
        log.warning("RESEND_API_KEY not configured — skipping email send")
        return False

    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        log.warning("send_email called with no recipients — skipping")
        return False

    payload = {
        "from": _get_from_email(),
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    timeout = TIMEOUT_SECONDS
    if attachments:
        payload["attachments"] = attachments
        timeout = ATTACHMENT_TIMEOUT_SECONDS

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            r.raise_for_status()
            # Count only, on both paths. A scheduled report goes to up to 25
            # people and its subject is rendered from query results, so neither
            # the addresses nor the subject belong in the logs.
            log.info("Email sent to %d recipient(s)", len(recipients))
            return True
    except (httpx.HTTPError, ValueError) as e:
        log.error("Failed to send email to %d recipient(s): %s", len(recipients), e)
        return False


def attachment_from_text(filename: str, content: str) -> dict:
    """Build a Resend attachment from text (CSV, say)."""
    return {
        "filename": filename,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }


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
