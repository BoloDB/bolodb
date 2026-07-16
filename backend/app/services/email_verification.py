"""MyEmailVerifier integration — real-time email verification at signup.

Uses MyEmailVerifier's single-address REST API to validate email deliverability
before creating a user account. Blocks Invalid, Unknown, or Disposable
addresses; allows Valid and Catch-All.

Docs: https://client.myemailverifier.com/verifier/validate_single/{email}/{api_key}
"""

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://client.myemailverifier.com/verifier/validate_single"
TIMEOUT_SECONDS = 8.0


def _get_api_key() -> Optional[str]:
    """
    Retrieve the MyEmailVerifier API key from the environment.
    
    Returns:
    	str: The configured API key, or `None` when it is not set.
    """
    return os.environ.get("MYEMAILVERIFIER_API_KEY")


class EmailVerificationOutcome:
    """Structured verification outcome."""

    def __init__(
        self,
        allowed: bool,
        status: str,
        reason: str,
        disposable: bool = False,
        catch_all: bool = False,
        skipped: bool = False,
    ):
        """
        Initialize an email verification outcome.
        
        Parameters:
            allowed (bool): Whether the email is permitted.
            status (str): Normalized verification status.
            reason (str): Human-readable explanation for the outcome.
            disposable (bool): Whether the email domain is disposable.
            catch_all (bool): Whether the address belongs to a catch-all domain.
            skipped (bool): Whether verification was skipped.
        """
        self.allowed = allowed
        self.status = status
        self.reason = reason
        self.disposable = disposable
        self.catch_all = catch_all
        self.skipped = skipped


async def verify_email(email: str) -> EmailVerificationOutcome:
    """
    Verify an email address through MyEmailVerifier and determine whether signup is allowed.
    
    Parameters:
        email (str): Email address to verify.
    
    Returns:
        EmailVerificationOutcome: Verification result, including the decision, normalized status,
            diagnostic reason, service flags, and whether verification was skipped. Service
            configuration or request failures allow signup and mark the result as skipped.
    """
    api_key = _get_api_key()
    if not api_key:
        log.warning("MYEMAILVERIFIER_API_KEY not set — skipping verification")
        return EmailVerificationOutcome(
            allowed=True,
            status="skipped",
            reason="Verification service not configured",
            skipped=True,
        )

    url = f"{BASE_URL}/{email}/{api_key}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Email verification service call failed: %s", e.__class__.__name__)
        return EmailVerificationOutcome(
            allowed=True,
            status="error",
            reason="Verification service unavailable",
            skipped=True,
        )

    status = str(data.get("Status", "")).strip().lower()
    disposable = _to_bool(data.get("Disposable_Domain"))
    catch_all = _to_bool(data.get("catch_all"))
    diagnosis = data.get("Diagnosis", "")

    if disposable:
        return EmailVerificationOutcome(
            allowed=False,
            status=status or "disposable",
            reason="Please use a permanent email address (disposable domains are not allowed).",
            disposable=True,
            catch_all=catch_all,
        )

    if status in {"invalid"}:
        return EmailVerificationOutcome(
            allowed=False,
            status=status,
            reason=diagnosis or "This email address doesn't appear to exist.",
            disposable=False,
            catch_all=catch_all,
        )

    if status in {"unknown"}:
        return EmailVerificationOutcome(
            allowed=False,
            status=status,
            reason="We couldn't verify this email address. Please try a different one.",
            disposable=False,
            catch_all=catch_all,
        )

    # Explicitly allow only "valid" or "catch_all" statuses
    if status in {"valid"} or (status == "catch_all" or catch_all):
        return EmailVerificationOutcome(
            allowed=True,
            status=status or "catch_all" if catch_all else "valid",
            reason="",
            disposable=False,
            catch_all=catch_all,
        )

    # Reject missing or unrecognized statuses
    return EmailVerificationOutcome(
        allowed=False,
        status=status or "unrecognized",
        reason="We couldn't verify this email address. Please try a different one.",
        disposable=False,
        catch_all=catch_all,
    )


def _to_bool(v) -> bool:
    """
    Convert a value to a boolean using recognized string representations.
    
    Parameters:
        v: The value to convert.
    
    Returns:
        bool: `True` for boolean `True`, strings representing true, or truthy values; `False` otherwise.
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes"}
    return bool(v)
