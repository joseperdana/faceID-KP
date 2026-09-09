"""Kiosk endpoints: pages, geofencing, upload validation and manual fallback."""

import io
from unittest.mock import patch

import pytest

from core import config
from routers.kiosk import calculate_distance, check_geofence
from services.db_service import DBService

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

CHURCH = (-7.979261, 112.625760)


def _file(content=JPEG, name="f.jpg", mime="image/jpeg"):
    return {"file": (name, io.BytesIO(content), mime)}


def _at_church():
    return {"lat": str(CHURCH[0]), "lng": str(CHURCH[1])}


# --- pages ----------------------------------------------------------------


def test_kiosk_page_is_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_photobooth_page_is_public(client):
    assert client.get("/photobooth").status_code == 200


def test_healthz_reports_face_recognition_state(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["face_recognition"] in ("ready", "unavailable")


# --- geofence maths -------------------------------------------------------


def test_haversine_matches_known_distance():
    # Roughly one degree of latitude at the equator is ~111 km.
    assert calculate_distance(0, 0, 1, 0) == pytest.approx(111_195, rel=0.01)


def test_distance_is_symmetric():
    a = calculate_distance(*CHURCH, -7.9734182, 112.6322894)
    b = calculate_distance(-7.9734182, 112.6322894, *CHURCH)
    assert a == pytest.approx(b)


def test_the_two_documented_church_coordinates_disagree():
    """Guards the coordinate confusion the audit found.

    The code and tasks/implementation_plan.md carried different coordinates,
    roughly a kilometre apart — far outside any 200 m radius, so at most one of
    them can be right. Whichever is configured must be verified on a map.
    """
    gap = calculate_distance(*CHURCH, -7.9734182, 112.6322894)
    assert gap > config.GEOFENCE_RADIUS_METERS


# --- geofence policy ------------------------------------------------------


def test_at_the_church_is_allowed():
    assert check_geofence(*CHURCH, 20.0) is None


def test_far_away_with_a_good_fix_is_rejected():
    response = check_geofence(-6.2088, 106.8456, 15.0)  # Jakarta
    assert response is not None and response.status_code == 403


def test_poor_indoor_accuracy_is_not_punished():
    """Indoors the browser often falls back to a wifi fix accurate to kilometres.

    Rejecting on raw distance would turn away members standing at the kiosk, so
    a fix only fails when it is outside the radius by more than its own error.
    """
    # 800 m away on paper, but the fix itself is only accurate to 5 km.
    assert check_geofence(-7.9865, 112.6255, 5000.0) is None


def test_missing_coordinates_are_rejected_when_enforcing():
    response = check_geofence(None, None, None)
    assert response is not None and response.status_code == 403
    assert "Manual" in response.body.decode()


def test_out_of_range_coordinates_are_rejected():
    response = check_geofence(999.0, 999.0, 1.0)
    assert response is not None and response.status_code == 400


def test_geofence_disabled_allows_everything():
    with patch.object(config, "ENABLE_GEOFENCE", False):
        assert check_geofence(-6.2088, 106.8456, 5.0) is None
        assert check_geofence(None, None, None) is None


# --- upload validation ----------------------------------------------------


def test_non_image_upload_is_refused_before_reaching_the_decoder(client):
    """Arbitrary bytes used to be handed straight to OpenCV's native decoders."""
    response = client.post(
        "/api/recognize",
        files={"file": ("payload.jpg", io.BytesIO(b"MZ\x90\x00 not an image"), "image/jpeg")},
        data=_at_church(),
    )
    assert response.status_code == 415


def test_oversized_upload_is_refused(client):
    oversized = JPEG + b"\x00" * (config.MAX_IMAGE_BYTES + 10)
    response = client.post(
        "/api/recognize",
        files={"file": ("big.jpg", io.BytesIO(oversized), "image/jpeg")},
        data=_at_church(),
    )
    assert response.status_code == 413


def test_png_is_accepted(client):
    with patch("face_service.FaceService.get_embedding", return_value=None):
        response = client.post(
            "/api/recognize", files=_file(PNG, "f.png", "image/png"), data=_at_church()
        )
    assert response.status_code == 400  # no face, but the format was accepted


def test_recognize_rejects_far_location_before_running_inference(client):
    with patch("face_service.FaceService.get_embedding") as embed:
        response = client.post(
            "/api/recognize", files=_file(), data={"lat": "-6.2088", "lng": "106.8456"}
        )
    assert response.status_code == 403
    embed.assert_not_called()


# --- manual fallback ------------------------------------------------------


def test_manual_checkin_records_method_manual(kiosk_client):
    with (
        patch.object(
            DBService, "get_user_by_id", return_value=[{"id": 1, "full_name": "Jonathan Kristi"}]
        ),
        patch.object(DBService, "check_user_log_today", return_value=[]),
        patch.object(
            DBService, "get_attendance_summary", return_value={"total": 2, "last_seen": None}
        ),
        patch.object(DBService, "insert_log") as insert,
    ):
        response = kiosk_client.post(
            "/api/attendance/manual-checkin", data={"user_id": 1, **_at_church()}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["method"] == "manual"
    assert insert.call_args[0][0]["method"] == "manual"


def test_manual_checkin_duplicate_is_flagged_distinctly(kiosk_client):
    existing = [{"id": 5, "timestamp": "2026-09-12T09:48:00+00:00", "method": "face"}]
    with (
        patch.object(
            DBService, "get_user_by_id", return_value=[{"id": 1, "full_name": "Jonathan Kristi"}]
        ),
        patch.object(DBService, "check_user_log_today", return_value=existing),
        patch.object(
            DBService, "get_attendance_summary", return_value={"total": 2, "last_seen": None}
        ),
        patch.object(DBService, "insert_log") as insert,
    ):
        response = kiosk_client.post(
            "/api/attendance/manual-checkin", data={"user_id": 1, **_at_church()}
        )

    assert response.json()["status"] == "already_checked_in"
    insert.assert_not_called()


def test_manual_checkin_unknown_user_returns_404(kiosk_client):
    with patch.object(DBService, "get_user_by_id", return_value=[]):
        response = kiosk_client.post(
            "/api/attendance/manual-checkin", data={"user_id": 999, **_at_church()}
        )
    assert response.status_code == 404


# --- search ---------------------------------------------------------------


def test_search_never_returns_phone_numbers(kiosk_client):
    """The endpoint used to double as a contact-list export."""
    rows = [{"id": 1, "full_name": "Jonathan Kristi"}]
    with patch.object(DBService, "search_active_users", return_value=rows) as search:
        response = kiosk_client.get("/api/users/search?q=Jo")

    assert response.status_code == 200
    for row in response.json()["data"]:
        assert "phone_number" not in row
    search.assert_called_once()


def test_search_requires_at_least_two_characters(kiosk_client):
    with patch.object(DBService, "search_active_users") as search:
        response = kiosk_client.get("/api/users/search?q=a")
    assert response.json()["data"] == []
    search.assert_not_called()


@pytest.mark.parametrize("hostile", ["a,b", "a(b)", "a%b", "a*", "a:b", "a;b"])
def test_search_rejects_postgrest_filter_metacharacters(hostile):
    """`or_()` is an expression language; comma, dot and parens are syntax there.

    Interpolating raw input let a caller graft extra OR branches onto the query
    and read rows that were meant to be hidden.
    """
    assert DBService.search_active_users(hostile) == []


# --- registration ---------------------------------------------------------


def test_registration_requires_consent(kiosk_client):
    """Biometric data is data pribadi spesifik under UU 27/2022."""
    response = kiosk_client.post(
        "/api/register",
        data={
            "full_name": "Jemaat Baru",
            "gender": "Pria",
            "phone_number": "08123456789",
            "consent": "false",
            **_at_church(),
        },
        files=[("files", ("a.jpg", io.BytesIO(JPEG), "image/jpeg"))],
    )
    assert response.status_code == 400
    assert "persetujuan" in response.json()["detail"].lower()


def test_registration_stores_consent_timestamp(kiosk_client):
    with (
        patch("face_service.FaceService.get_embedding", return_value=[1.0] * 512),
        patch.object(DBService, "get_user_by_name", return_value=[]),
        patch.object(DBService, "match_faces", return_value=[]),
        patch.object(DBService, "insert_user", return_value={"id": 42}) as insert_user,
        patch.object(DBService, "insert_log"),
    ):
        response = kiosk_client.post(
            "/api/register",
            data={
                "full_name": "Jemaat Baru",
                "gender": "Pria",
                "phone_number": "08123456789",
                "consent": "true",
                **_at_church(),
            },
            files=[("files", ("a.jpg", io.BytesIO(JPEG), "image/jpeg"))],
        )

    assert response.status_code == 200
    stored = insert_user.call_args[0][0]
    assert stored["consent_at"]
    assert stored["consent_version"] == "1.0"


def test_registration_uses_the_looser_duplicate_threshold(kiosk_client):
    with (
        patch("face_service.FaceService.get_embedding", return_value=[1.0] * 512),
        patch.object(DBService, "get_user_by_name", return_value=[]),
        patch.object(DBService, "match_faces", return_value=[]) as match,
        patch.object(DBService, "insert_user", return_value={"id": 42}),
        patch.object(DBService, "insert_log"),
    ):
        kiosk_client.post(
            "/api/register",
            data={
                "full_name": "Jemaat Baru",
                "gender": "Pria",
                "phone_number": "08123456789",
                "consent": "true",
                **_at_church(),
            },
            files=[("files", ("a.jpg", io.BytesIO(JPEG), "image/jpeg"))],
        )

    assert match.call_args[0][1] == config.FACE_DUPLICATE_THRESHOLD


def test_registration_respects_the_geofence(kiosk_client):
    """Registration writes an attendance row, so skipping the check bypassed it."""
    response = kiosk_client.post(
        "/api/register",
        data={
            "full_name": "Jemaat Baru",
            "gender": "Pria",
            "phone_number": "08123456789",
            "consent": "true",
            "lat": "-6.2088",
            "lng": "106.8456",
        },
        files=[("files", ("a.jpg", io.BytesIO(JPEG), "image/jpeg"))],
    )
    assert response.status_code == 403


def test_registration_rejects_too_many_files(kiosk_client):
    files = [
        ("files", (f"{i}.jpg", io.BytesIO(JPEG), "image/jpeg"))
        for i in range(config.MAX_REGISTER_FILES + 2)
    ]
    response = kiosk_client.post(
        "/api/register",
        data={
            "full_name": "Jemaat Baru",
            "gender": "Pria",
            "phone_number": "08123456789",
            "consent": "true",
            **_at_church(),
        },
        files=files,
    )
    assert response.status_code == 400
