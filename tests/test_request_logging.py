"""Log terstruktur per request, per check-in, dan per 429.

Yang diuji adalah kontrak baris log (nama field, nilai, dan apa yang TIDAK
boleh ikut tercatat), karena Grafana/Loki dan agen lain bergantung padanya.
Semua akses ke Supabase dan model wajah di-patch.
"""
import json
import logging
import re
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from core import observability
from core.logging_setup import JsonFormatter, sanitize_device, setup_logging
from routers import kiosk

client = TestClient(app)

FAKE_VECTOR = [0.01] * 512
MATCH = [{"id": 7, "full_name": "Budi Santoso", "similarity": 0.81234}]


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.raw = []

    def emit(self, record):
        self.raw.append(self.format(record))

    def lines(self, logger=None):
        parsed = [json.loads(r) for r in self.raw]
        return [p for p in parsed if logger is None or p["logger"] == logger]


@pytest.fixture(autouse=True)
def no_sentry_delivery():
    """.env lokal bisa berisi DSN sungguhan. Tes di sini sengaja memicu 500 dan
    429 — jangan sampai itu mengotori project Sentry produksi."""
    import sentry_sdk
    with patch.object(sentry_sdk.get_client(), "capture_event", return_value=None):
        yield


@pytest.fixture
def logs():
    handler = _Capture()
    kp_logger = logging.getLogger("kp")
    kp_logger.addHandler(handler)
    yield handler
    kp_logger.removeHandler(handler)


@contextmanager
def face_db(match=MATCH, today_log=(), insert_side_effect=None):
    with patch("routers.kiosk.face_service.get_embedding", return_value=FAKE_VECTOR), \
         patch("services.db_service.DBService.match_faces", return_value=list(match)), \
         patch("services.db_service.DBService.get_user_link_info", return_value={}), \
         patch("services.db_service.DBService.check_user_log_today", return_value=list(today_log)), \
         patch("services.db_service.DBService.get_user_history", return_value=[]), \
         patch("services.db_service.DBService.insert_log", side_effect=insert_side_effect):
        yield


def _recognize(**data):
    return client.post(
        "/api/recognize",
        data=data,
        files={"file": ("scan.jpg", b"fake image bytes", "image/jpeg")},
        headers={"X-KP-Device": "kiosk-03"},
    )


# --- kp.request ---------------------------------------------------------------

def test_request_line_has_context_status_and_duration(logs):
    response = client.get("/api/users/search?q=", headers={"X-KP-Device": "kiosk-03"})
    assert response.status_code == 200

    [line] = [l for l in logs.lines("kp.request") if l["path"] == "/api/users/search"]
    assert line["method"] == "GET"
    assert line["route"] == "/api/users/search"
    assert line["status"] == 200
    assert isinstance(line["duration_ms"], float)
    assert line["client_ip"] == "testclient"
    assert line["device"] == "kiosk-03"
    assert line["request_id"] == response.headers["x-request-id"]
    for field in ("ts", "level", "logger", "msg", "release", "env"):
        assert field in line
    assert line["ts"].endswith("Z")
    # Query string bisa berisi potongan nama yang dicari — tidak boleh ikut.
    assert "q=" not in json.dumps(line)


def test_route_template_is_logged_not_raw_path(logs):
    response = client.get("/api/attendance/date/2026-01-01")
    assert response.status_code == 401  # tanpa cookie admin; rute tetap cocok
    [line] = logs.lines("kp.request")
    assert line["route"] == "/api/attendance/date/{target_date}"
    assert line["path"] == "/api/attendance/date/2026-01-01"


def test_inbound_request_id_is_echoed():
    response = client.get("/api/users/search?q=", headers={"X-Request-ID": "abcDEF12-3456"})
    assert response.headers["x-request-id"] == "abcDEF12-3456"


@pytest.mark.parametrize("bad", ["short", "has space in it", "x" * 65, "semi;colon-12345"])
def test_invalid_inbound_request_id_is_replaced(bad):
    response = client.get("/api/users/search?q=", headers={"X-Request-ID": bad})
    rid = response.headers["x-request-id"]
    assert rid != bad
    assert re.fullmatch(r"[0-9a-f]{16}", rid)


@pytest.mark.parametrize("raw,expected", [
    ("kiosk-03", "kiosk-03"),
    ("Kiosk 03", "kiosk-03"),
    ("anon-7f3a", "anon-7f3a"),
    ("../../etc/passwd", "etc-passwd"),
    ("<script>", "script"),
    ("!!!", "unknown"),
    ("", "unknown"),
    (None, "unknown"),
    ("a" * 100, "a" * 40),
])
def test_sanitize_device(raw, expected):
    assert sanitize_device(raw) == expected


def test_device_header_is_sanitized_in_log(logs):
    client.get("/api/users/search?q=", headers={"X-KP-Device": "Kiosk 03 <b>"})
    [line] = logs.lines("kp.request")
    assert line["device"] == "kiosk-03-b"


def test_missing_device_header_logs_unknown(logs):
    client.get("/api/users/search?q=")
    [line] = logs.lines("kp.request")
    assert line["device"] == "unknown"


def test_static_and_favicon_are_not_logged_but_still_get_request_id(logs):
    response = client.get("/static/js/index.js")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")
    client.get("/favicon.ico")
    assert logs.lines("kp.request") == []


def test_health_200_is_not_logged_but_503_is(logs):
    with patch("routers.observability._check_database", return_value="ok"), \
         patch("routers.observability._check_face_model", return_value="loaded"):
        assert client.get("/health").status_code == 200
    assert logs.lines("kp.request") == []

    with patch("routers.observability._check_database", return_value="ok"), \
         patch("routers.observability._check_face_model", return_value="unavailable"):
        assert client.get("/health").status_code == 503
    [line] = logs.lines("kp.request")
    assert line["status"] == 503
    assert line["level"] == "error"


def test_unhandled_exception_is_logged_as_500_and_reraised(logs):
    safe_client = TestClient(app, raise_server_exceptions=False)
    with patch("routers.kiosk.face_service.get_embedding", return_value=FAKE_VECTOR), \
         patch("services.db_service.DBService.match_faces", side_effect=RuntimeError("supabase down")):
        response = safe_client.post(
            "/api/recognize", files={"file": ("scan.jpg", b"x", "image/jpeg")}
        )
    assert response.status_code == 500

    [req] = logs.lines("kp.request")
    assert req["status"] == 500
    assert req["level"] == "error"
    assert "RuntimeError" in req["exc"]

    [checkin] = logs.lines("kp.checkin")
    assert checkin["outcome"] == "error"
    assert checkin["failed_stage"] == "match"
    assert checkin["error_type"] == "RuntimeError"


def test_stdout_receives_one_json_object_per_line(capsys):
    client.get("/api/users/search?q=", headers={"X-KP-Device": "kiosk-03"})
    out = [l for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    parsed = [json.loads(l) for l in out]
    assert any(p["logger"] == "kp.request" and p["path"] == "/api/users/search" for p in parsed)


def test_setup_logging_is_idempotent():
    setup_logging()
    setup_logging()
    marked = [h for h in logging.getLogger("kp").handlers if getattr(h, "_kp_json_handler", False)]
    assert len(marked) == 1


# --- kp.ratelimit -------------------------------------------------------------

def test_rate_limit_logs_warning_and_keeps_slowapi_response(logs):
    # Storage limiter hidup sepanjang sesi pytest; tes lain sudah memakai jatahnya.
    kiosk.limiter.reset()
    observability._throttle_state.clear()
    try:
        with patch("core.observability.capture_event") as mock_capture:
            statuses = [
                client.get("/api/users/search?q=", headers={"X-KP-Device": "kiosk-07"}).status_code
                for _ in range(62)
            ]
            last = client.get("/api/users/search?q=", headers={"X-KP-Device": "kiosk-07"})
    finally:
        kiosk.limiter.reset()
        observability._throttle_state.clear()

    assert statuses[:60] == [200] * 60
    assert statuses[60:] == [429, 429]
    assert last.status_code == 429
    # Persis respons _rate_limit_exceeded_handler milik slowapi.
    assert last.json() == {"error": "Rate limit exceeded: 60 per 1 minute"}
    assert last.headers.get("x-request-id")

    rl = logs.lines("kp.ratelimit")
    assert len(rl) == 3  # setiap 429 tercatat di log
    assert rl[0]["level"] == "warning"
    assert rl[0]["route"] == "/api/users/search"
    assert rl[0]["client_ip"] == "testclient"
    assert rl[0]["device"] == "kiosk-07"
    assert rl[0]["limit"] == "60 per 1 minute"

    # ...tapi Sentry hanya sekali per rute per 60 detik.
    assert mock_capture.call_count == 1
    assert mock_capture.call_args.kwargs["route"] == "/api/users/search"

    statuses_429 = [l["status"] for l in logs.lines("kp.request") if l["status"] == 429]
    assert len(statuses_429) == 3


# --- kp.checkin ---------------------------------------------------------------

def test_face_checkin_success_logs_stages_without_pii(logs):
    with face_db():
        response = _recognize()
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    [line] = logs.lines("kp.checkin")
    assert line["method"] == "face"
    assert line["outcome"] == "success"
    assert line["user_id"] == 7
    assert line["similarity"] == 0.812
    assert line["device"] == "kiosk-03"
    assert set(line["stage_ms"]) >= {"embedding", "match", "link_info", "check_today", "history", "insert", "total"}
    assert all(isinstance(v, float) for v in line["stage_ms"].values())

    [req] = logs.lines("kp.request")
    assert req["request_id"] == line["request_id"] == response.headers["x-request-id"]

    raw = "\n".join(logs.raw)
    assert "Budi" not in raw


def test_face_checkin_already_checked_in(logs):
    with face_db(today_log=[{"id": 1}]):
        assert _recognize().status_code == 200
    [line] = logs.lines("kp.checkin")
    assert line["outcome"] == "already_checked_in"
    assert "insert" not in line["stage_ms"]


def test_face_checkin_duplicate_race(logs):
    with face_db(insert_side_effect=Exception("23505 duplicate key value violates unique constraint")):
        response = _recognize()
    assert response.status_code == 200
    [line] = logs.lines("kp.checkin")
    assert line["outcome"] == "duplicate_race"


def test_face_checkin_unknown_face(logs):
    with face_db(match=[]):
        response = _recognize()
    assert response.json()["status"] == "unknown"
    [line] = logs.lines("kp.checkin")
    assert line["outcome"] == "unknown_face"
    assert "user_id" not in line


def test_face_checkin_no_face(logs):
    with patch("routers.kiosk.face_service.get_embedding", return_value=None):
        response = _recognize()
    assert response.status_code == 400
    [line] = logs.lines("kp.checkin")
    assert line["outcome"] == "no_face"
    assert "embedding" in line["stage_ms"]


def test_geofence_rejection_logs_distance_not_coordinates(logs):
    import os
    with patch.dict(os.environ, {"ENABLE_GEOFENCE": "true"}):
        response = _recognize(lat="-6.200000", lng="106.816666")
    assert response.status_code == 403
    [line] = logs.lines("kp.checkin")
    assert line["outcome"] == "geofence_rejected"
    assert isinstance(line["geofence_distance_m"], int) and line["geofence_distance_m"] > 600000
    raw = "\n".join(logs.raw)
    assert "106.8" not in raw and "-6.2" not in raw


def test_manual_checkin_logs_manual_method(logs):
    with patch("services.db_service.DBService.get_user_by_id", return_value=[{"id": 1, "full_name": "Jonathan Kristi"}]), \
         patch("services.db_service.DBService.check_user_log_today", return_value=[]), \
         patch("services.db_service.DBService.get_user_history", return_value=[]), \
         patch("services.db_service.DBService.insert_log"):
        response = client.post("/api/attendance/manual-checkin", data={"user_id": 1})
    assert response.status_code == 200
    [line] = logs.lines("kp.checkin")
    assert line["method"] == "manual"
    assert line["outcome"] == "success"
    assert line["user_id"] == 1
    assert "similarity" not in line
    assert {"get_user", "check_today", "history", "insert", "total"} <= set(line["stage_ms"])
    assert "Jonathan" not in "\n".join(logs.raw)


# --- fail-safe ----------------------------------------------------------------

def test_logging_failure_never_breaks_a_checkin():
    """Formatter, logger, konteks, dan Sentry dibuat gagal sekaligus — absensi harus tetap jalan."""
    def boom(*a, **k):
        raise RuntimeError("logging broken")

    class ExplodingSentry:
        """Setiap pemakaian Sentry DARI KODE KITA meledak.

        Sengaja mengganti nama `sentry_sdk` di core.observability saja, bukan
        mem-patch atribut modul sentry_sdk global. Sejak sentry-sdk 2.70,
        integrasi httpx-nya ikut membungkus TestClient dan memanggil
        sentry_sdk.start_span — patch global membuat klien uji itu sendiri yang
        meledak, bukan aplikasi yang sedang diuji.
        """
        def __getattr__(self, name):
            raise RuntimeError(f"sentry broken: {name}")

    with patch.object(JsonFormatter, "format", boom), \
         patch.object(logging.getLogger("kp.checkin"), "log", boom), \
         patch.object(logging.getLogger("kp.request"), "log", boom), \
         patch("main.resolve_request_id", boom), \
         patch("core.observability.sentry_sdk", ExplodingSentry()), \
         patch("logging.raiseExceptions", False), \
         face_db():
        response = _recognize()
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["method"] == "face"
