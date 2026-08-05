"""What kind of thing a JWT is, and the one place that vocabulary is written down.

Every token this app issues is signed with the same secret, so a valid signature
says only "we minted this" — not what we minted it *for*. Without a claim naming
the kind, a refresh token, a password-reset token and a Slack OAuth state are all
interchangeable with a session cookie: each carries a ``user_id``, each verifies,
and ``get_current_user`` could not tell them apart. Labelling them is what makes
a token usable only where it was meant to be used.
"""

# The claim carrying the kind. Named after the JOSE header field of the same
# meaning, but kept in the payload — the header is not something we read, and
# only the payload is covered by the signature check we do.
TYPE_CLAIM = "typ"

# The user's token generation at the moment this token was minted. Compared
# against the stored one on every request, so raising that number retires every
# token issued before it. Absent means 0 — the value a user starts at — so a
# token predating this claim stays valid until something actually revokes it.
VERSION_CLAIM = "ver"

ACCESS = "access"
REFRESH = "refresh"
PASSWORD_RESET = "password_reset"
SLACK_OAUTH_STATE = "slack_oauth_state"


def is_kind(payload, kind: str) -> bool:
    """Whether ``payload`` is a token of ``kind``.

    Strict on purpose: a token carrying no type claim is rejected rather than
    assumed to be an access token. Tokens minted before this claim existed are
    exactly the ones already in circulation — and so exactly the ones that could
    already have been stolen — so grandfathering them in would leave the hole
    open for the population that matters. The cost is that everyone signs in
    once after this deploys.
    """
    return isinstance(payload, dict) and payload.get(TYPE_CLAIM) == kind
