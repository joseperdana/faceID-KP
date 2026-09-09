"""Shared test fixtures.

The environment is populated before any application module is imported, so
core.config validates against known-good values rather than whatever happens to
be in a developer's .env.
"""

import os

import pytest

TEST_ENV = {
    "SUPABASE_URL": "https://fake.supabase.co",
    "SUPABASE_KEY": "test-anon-key",
    "SECRET_KEY": "ci-only-secret-key-not-for-production-use",
    "ADMIN_PASSWORD": "ci-only-password",
    "KIOSK_TOKEN": "ci-only-kiosk-token-value-123456",
    "ENABLE_GEOFENCE": "true",
    "CHURCH_LAT": "-7.979261",
    "CHURCH_LNG": "112.625760",
    "GEOFENCE_RADIUS_METERS": "200",
    "COOKIE_SECURE": "false",
    "ENVIRONMENT": "test",
    "SENTRY_DSN": "",
}
for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)


@pytest.fixture(scope="session")
def client():
    """TestClient with the FastAPI lifespan disabled.

    Running the lifespan would try to download and load the face model, which
    is several hundred megabytes and irrelevant to these tests.
    """
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def kiosk_client(client):
    """A client that presents a valid kiosk device token."""
    client.headers.update({"X-Kiosk-Token": os.environ["KIOSK_TOKEN"]})
    yield client
    client.headers.pop("X-Kiosk-Token", None)


@pytest.fixture()
def admin_client(client):
    """A client holding a valid admin session cookie."""
    from core.security import COOKIE_NAME, create_access_token

    token = create_access_token({"sub": "admin"})
    client.cookies.set(COOKIE_NAME, token)
    yield client
    client.cookies.clear()


# --- Playwright fixtures (end-to-end suite only) -------------------------


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "permissions": ["geolocation", "camera"],
        "geolocation": {"latitude": -7.979261, "longitude": 112.625760},
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "args": [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--allow-file-access-from-files",
        ],
    }
