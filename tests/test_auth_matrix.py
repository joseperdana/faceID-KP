"""Every endpoint's authentication requirement, asserted explicitly.

An audit found four endpoints reachable by anyone that should not have been:
/api/register, /api/update-face, /api/attendance/manual-checkin and
/api/users/search. Those are regressions that are easy to reintroduce by adding
a route to the wrong router, so the expectation is written down here rather than
left to review.
"""

from unittest.mock import patch

import pytest

from services.db_service import DBService

# (method, path, who may call it)
#   "public" — no credentials at all
#   "kiosk"  — an enrolled kiosk device or an admin
#   "admin"  — a signed-in pengurus only
ENDPOINTS = [
    ("GET", "/", "public"),
    ("GET", "/photobooth", "public"),
    ("GET", "/login", "public"),
    ("POST", "/api/login", "public"),
    ("POST", "/api/recognize", "public"),
    ("POST", "/api/photobooth/upload", "public"),
    ("GET", "/register", "kiosk"),
    ("GET", "/api/users/search", "kiosk"),
    ("POST", "/api/attendance/manual-checkin", "kiosk"),
    ("POST", "/api/register", "kiosk"),
    ("GET", "/dashboard", "admin"),
    ("GET", "/kiosk/enroll", "admin"),
    ("POST", "/api/update-face", "admin"),
    ("GET", "/api/users", "admin"),
    ("PUT", "/api/users/1", "admin"),
    ("DELETE", "/api/users/1", "admin"),
    ("DELETE", "/api/users/1/biometrics", "admin"),
    ("GET", "/api/users/1/history", "admin"),
    ("GET", "/api/dashboard-stats", "admin"),
    ("GET", "/api/analytics", "admin"),
    ("GET", "/api/all-logs", "admin"),
    ("GET", "/api/attendance/date/2026-09-12", "admin"),
    ("DELETE", "/api/logs/1", "admin"),
    ("GET", "/api/export-excel", "admin"),
]

PROTECTED = [entry for entry in ENDPOINTS if entry[2] != "public"]
ADMIN_ONLY = [entry for entry in ENDPOINTS if entry[2] == "admin"]


def _call(client, method, path):
    return client.request(method, path, follow_redirects=False)


def _is_rejected(response) -> bool:
    """401 for API calls, 303 to /login for page routes."""
    if response.status_code == 401:
        return True
    return response.status_code == 303 and response.headers.get("location") == "/login"


@pytest.mark.parametrize("method,path,scope", PROTECTED, ids=lambda v: str(v))
def test_protected_endpoints_reject_anonymous(client, method, path, scope):
    assert _is_rejected(_call(client, method, path)), (
        f"{method} {path} is reachable without credentials"
    )


@pytest.mark.parametrize("method,path,scope", ADMIN_ONLY, ids=lambda v: str(v))
def test_admin_only_endpoints_reject_kiosk_token(kiosk_client, method, path, scope):
    """A kiosk device must not be able to perform admin actions.

    /api/update-face is the one that matters most: overwriting an embedding
    locks the real person out of the system and cannot be undone.
    """
    assert _is_rejected(_call(kiosk_client, method, path)), (
        f"{method} {path} is reachable with only a kiosk token"
    )


def test_kiosk_scope_accepts_enrolled_device(kiosk_client):
    """An enrolled device reaches kiosk endpoints without an admin password."""
    with patch.object(DBService, "search_active_users", return_value=[]):
        response = kiosk_client.get("/api/users/search?q=ab")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_kiosk_scope_accepts_admin_session(admin_client):
    response = admin_client.get("/register", follow_redirects=False)
    assert response.status_code == 200


def test_static_mount_does_not_expose_dashboard(client):
    """/static must not serve the HTML pages behind authentication.

    The whole `frontend/` directory used to be mounted, so /static/dashboard.html
    returned the dashboard with no session at all.
    """
    for path in ("/static/dashboard.html", "/static/register.html", "/static/index.html"):
        assert client.get(path).status_code == 404, f"{path} is still served"


def test_security_headers_present(client):
    response = client.get("/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "camera=(self)" in response.headers["Permissions-Policy"]


def test_logout_clears_cookie(admin_client):
    response = admin_client.get("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    # The cookie has to be cleared on the redirect response itself; setting it
    # on an injected Response object had no effect on what was actually sent.
    assert "faceid_token" in response.headers.get("set-cookie", "")
