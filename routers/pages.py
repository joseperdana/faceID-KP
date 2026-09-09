"""HTML page routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from core.security import (
    check_admin_auth,
    check_kiosk_auth,
    clear_admin_cookie,
    set_kiosk_cookie,
)

router = APIRouter(tags=["pages"])


def _page(name: str) -> FileResponse:
    # no-store keeps a shared kiosk tablet from serving a cached page that was
    # rendered for a different session.
    return FileResponse(f"frontend/{name}", headers={"Cache-Control": "no-store"})


@router.get("/")
def kiosk_page():
    return _page("index.html")


@router.get("/photobooth")
def photobooth_page():
    return _page("photobooth.html")


@router.get("/login")
def login_page():
    return _page("login.html")


@router.get("/register")
def register_page(auth: bool = Depends(check_kiosk_auth)):
    """Newcomer registration.

    Reachable from an enrolled kiosk without an admin password. It used to
    require a full admin session, which meant a newcomer who failed recognition
    was sent to a password prompt, and a pengurus had to type the admin password
    on a public tablet in front of the queue.
    """
    return _page("register.html")


@router.get("/dashboard")
def dashboard_page(auth: bool = Depends(check_admin_auth)):
    return _page("dashboard.html")


@router.get("/kiosk/enroll", response_class=HTMLResponse)
def kiosk_enroll(request: Request, auth: bool = Depends(check_admin_auth)):
    """One-time device enrolment, performed by a pengurus on the kiosk tablet.

    Stores a long-lived device cookie so the tablet can run check-in and
    registration without anyone staying logged in, while those endpoints remain
    closed to the internet.
    """
    response = RedirectResponse(url="/", status_code=303)
    set_kiosk_cookie(response)
    return response


@router.get("/logout")
def logout():
    # The cookie must be cleared on the response that is actually returned;
    # setting it on an injected Response object had no effect on the redirect.
    response = RedirectResponse(url="/login", status_code=303)
    clear_admin_cookie(response)
    return response
