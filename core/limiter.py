"""One shared rate limiter for the whole application.

Three separate Limiter instances used to exist (main.py, routers/auth.py,
routers/kiosk.py), each with its own in-memory store, so the "5 attempts per
minute" brute-force guard on login was really 5-per-instance-per-worker.

Client identity also needs care. The app sits behind nginx with
`proxy_pass http://127.0.0.1:8000`, so `get_remote_address` sees 127.0.0.1 for
every request and the whole congregation shares one bucket. We read the
forwarded address instead, but only trust it when the immediate peer is the
local reverse proxy — otherwise anyone could spoof X-Forwarded-For and escape
their own limit.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from core import config

# Peers we accept forwarded headers from. The app binds to 127.0.0.1 and is only
# reachable through the local nginx, so this is the complete set.
_TRUSTED_PROXIES = {"127.0.0.1", "::1", "localhost"}


def client_identifier(request: Request) -> str:
    """Best available identity for rate limiting.

    A kiosk that has been enrolled gets its own bucket keyed by the device
    token, so one busy tablet cannot exhaust the quota for phones on the same
    church wifi (they all share a single public IP behind NAT).
    """
    kiosk_token = request.cookies.get(KIOSK_COOKIE_NAME)
    if kiosk_token and config.KIOSK_TOKEN and kiosk_token == config.KIOSK_TOKEN:
        return "kiosk-device"

    peer = request.client.host if request.client else None
    if peer in _TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Left-most entry is the original client; nginx appends, so the
            # right-most entries are proxies we control.
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Imported here rather than from core.security to avoid a circular import;
# core.security imports this module for the login limiter.
KIOSK_COOKIE_NAME = "faceid_kiosk"

limiter = Limiter(
    key_func=client_identifier,
    storage_uri=config.RATE_LIMIT_STORAGE_URI,
)
