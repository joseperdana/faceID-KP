"""Authentication: admin sessions and enrolled kiosk devices.

Two identities exist in this system and they need different treatment.

* **Admin (pengurus)** — signs in with a password, gets a short-lived JWT
  cookie, and may read and modify member data.
* **Kiosk device** — a tablet by the door with nobody logged in. It must be able
  to register a newcomer and run the manual-search fallback, but it must not be
  the internet at large. An admin enrols the tablet once by opening
  /kiosk/enroll on it; that stores a long-lived device cookie holding the shared
  KIOSK_TOKEN.

This replaces the previous arrangement where /api/register, /api/update-face,
/api/attendance/manual-checkin and /api/users/search were reachable by anyone,
while the /register *page* was locked behind the admin password — a gate on the
door with the window left open.
"""

import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Request, Response

from core import config
from core.limiter import KIOSK_COOKIE_NAME

SECRET_KEY = config.SECRET_KEY
ALGORITHM = "HS256"
COOKIE_NAME = "faceid_token"


# --- Token issuing / verification ----------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=config.SESSION_HOURS)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        # algorithms is pinned to a single symmetric algorithm, so neither
        # `alg: none` nor an RS256->HS256 confusion attack applies here.
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Sesi tidak valid")


# --- Cookie helpers -------------------------------------------------------

def set_admin_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=config.SESSION_HOURS * 3600,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def clear_admin_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def set_kiosk_cookie(response: Response) -> None:
    response.set_cookie(
        key=KIOSK_COOKIE_NAME,
        value=config.KIOSK_TOKEN,
        max_age=config.KIOSK_TOKEN_DAYS * 86400,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


# --- Identity checks ------------------------------------------------------

def _is_admin(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        verify_token(token)
        return True
    except HTTPException:
        return False


def _is_kiosk(request: Request) -> bool:
    """Constant-time comparison of the device token.

    Also accepts an X-Kiosk-Token header so a kiosk shell without cookie storage
    (or an automated smoke test) can authenticate.
    """
    if not config.KIOSK_TOKEN:
        return False
    presented = request.cookies.get(KIOSK_COOKIE_NAME) or request.headers.get(
        "x-kiosk-token"
    )
    if not presented:
        return False
    return hmac.compare_digest(presented, config.KIOSK_TOKEN)


async def check_admin_auth(request: Request) -> bool:
    """Require a signed-in pengurus. Used for the dashboard and member CRUD."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Belum masuk")
    verify_token(token)
    return True


async def check_kiosk_auth(request: Request) -> bool:
    """Require either an enrolled kiosk device or a signed-in pengurus.

    Applied to the endpoints that write attendance or read the member list.
    These are legitimate kiosk actions, so they cannot demand an admin password
    on a public tablet, but they must not be open to the internet either.
    """
    if _is_kiosk(request) or _is_admin(request):
        return True
    raise HTTPException(
        status_code=401,
        detail=(
            "Perangkat ini belum terdaftar sebagai kiosk. "
            "Minta pengurus membuka /kiosk/enroll di perangkat ini."
        ),
    )


def verify_admin_password(password: str) -> bool:
    """Check the submitted password without leaking timing information.

    Prefers a bcrypt hash. Falls back to a constant-time comparison against a
    plaintext ADMIN_PASSWORD so an existing deployment keeps working during the
    migration; core.config warns about that path at startup.
    """
    if config.ADMIN_PASSWORD_HASH:
        try:
            import bcrypt

            return bcrypt.checkpw(
                password.encode("utf-8"), config.ADMIN_PASSWORD_HASH.encode("utf-8")
            )
        except (ValueError, TypeError):
            # A malformed hash must never fall through to "access granted".
            return False
    if config.ADMIN_PASSWORD:
        return hmac.compare_digest(password, config.ADMIN_PASSWORD)
    return False
