"""Shared rate limiter.

A single ``Limiter`` instance lives here (not inside ``create_app``) so route
modules can reference it in ``@limiter.limit(...)`` decorators at import time,
which is how slowapi applies per-endpoint limits. ``server.py`` wires the same
instance onto ``app.state`` and registers the 429 handler.

Client identity: behind the bundled nginx the backend sees the proxy's IP on
every request, so a plain ``request.client.host`` key would put all users in one
bucket. We key on the first ``X-Forwarded-For`` hop that nginx sets, falling
back to the socket address. Note this trusts ``X-Forwarded-For``; the backend
must therefore only be reachable through the proxy (do not expose port 4321
directly in production), otherwise a client can spoof the header to dodge the
limit.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


def client_key(request):
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Left-most entry is the original client per nginx's proxy_add_x_forwarded_for.
        # comment made by somesh/Entropy-rgb , i think the rightmost shall be the original client id , and the left most can be fake id hence modyfying following code
        last = xff.split(",")[-1].strip()
        if last:
            return last
    return get_remote_address(request)


limiter = Limiter(key_func=client_key)
