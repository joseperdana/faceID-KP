from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_reports_ok_when_dependencies_up():
    """Health harus melaporkan tiap dependensi secara eksplisit, bukan sekadar 200.

    Kedua probe di-patch, sama seperti dua tes di bawah. Tanpa itu tes ini
    memanggil Supabase sungguhan: hijau di laptop yang punya .env berisi, merah
    di CI yang memakai kredensial palsu. Yang diuji di sini adalah kontrak
    pelaporan /health — bahwa probe yang sehat muncul sebagai "ok"/"loaded" dan
    statusnya 200 — bukan apakah infrastruktur sedang hidup. Kalau tes ini ikut
    memeriksa ketersediaan nyata, ia akan merah setiap Supabase gereja ngadat
    dan gate deploy kehilangan arti.
    """
    with patch("routers.observability._check_database", return_value="ok"), \
         patch("routers.observability._check_face_model", return_value="loaded"):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["face_model"] == "loaded"
    assert "release" in body and "environment" in body


def test_health_returns_503_when_database_is_down():
    """Ini inti kenapa /health ada: proses tetap hidup dan melayani halaman
    statis, tapi absensi lumpuh. Monitor eksternal harus ikut merah."""
    with patch("routers.observability._check_database", side_effect=RuntimeError("boom")):
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"].startswith("error:")


def test_health_returns_503_when_face_model_missing():
    with patch("routers.observability._check_face_model", return_value="unavailable"):
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["checks"]["face_model"] == "unavailable"


def test_client_error_is_forwarded_to_sentry():
    """Error browser (kamera ditolak, GPS timeout) harus sampai ke Sentry."""
    with patch("routers.observability.capture_event") as mock_capture:
        response = client.post("/api/client-error", json={
            "kind": "gps_error",
            "message": "User denied Geolocation",
            "page": "/",
        })
    assert response.status_code == 200
    mock_capture.assert_called_once()
    assert mock_capture.call_args.kwargs["where"] == "client.gps_error"


def test_client_error_rejects_oversized_payload():
    """Endpoint ini publik (kiosk tidak login), jadi payload wajib dibatasi."""
    response = client.post("/api/client-error", json={
        "kind": "js_error",
        "message": "x" * 5000,
    })
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /health — blok memori
# ---------------------------------------------------------------------------

_FAKE_STATUS = "Name:\tuvicorn\nVmPeak:\t 2000000 kB\nVmRSS:\t  1048576 kB\nThreads:\t12\n"
_FAKE_MEMINFO = (
    "MemTotal:        4028580 kB\n"
    "MemFree:          200000 kB\n"
    "MemAvailable:     512000 kB\n"
    "SwapTotal:       2097152 kB\n"
    "SwapFree:        1048576 kB\n"
)


def _fake_proc(path):
    return {"/proc/self/status": _FAKE_STATUS, "/proc/meminfo": _FAKE_MEMINFO}.get(path)


def test_health_reports_memory_from_proc():
    """H1 (VPS kehabisan RAM) hanya bisa dibuktikan kalau angka RAM & swap
    terlihat dari /health, yang sudah dipantau tiap menit dari luar."""
    with patch("routers.observability._check_database", return_value="ok"), \
         patch("routers.observability._check_face_model", return_value="loaded"), \
         patch("routers.observability._read_proc", side_effect=_fake_proc):
        response = client.get("/health")
    assert response.status_code == 200
    memory = response.json()["memory"]
    assert memory["process_rss_mb"] == 1024.0
    assert "rss_is_peak" not in memory
    assert memory["system_total_mb"] == round(4028580 / 1024, 1)
    assert memory["system_available_mb"] == 500.0
    assert memory["swap_total_mb"] == 2048.0
    assert memory["swap_used_mb"] == 1024.0
    assert isinstance(memory["pid"], int)


def test_health_memory_falls_back_to_peak_rss_without_proc():
    """Di macOS (laptop dev) tidak ada /proc: pakai ru_maxrss dan tandai sebagai puncak."""
    with patch("routers.observability._check_database", return_value="ok"), \
         patch("routers.observability._check_face_model", return_value="loaded"), \
         patch("routers.observability._read_proc", return_value=None):
        response = client.get("/health")
    memory = response.json()["memory"]
    assert memory["rss_is_peak"] is True
    assert memory["process_rss_mb"] > 0
    assert "system_total_mb" not in memory


def test_health_memory_failure_never_changes_status():
    """Memori hanya informasi: kegagalannya tidak boleh membuat /health merah."""
    with patch("routers.observability._check_database", return_value="ok"), \
         patch("routers.observability._check_face_model", return_value="loaded"), \
         patch("routers.observability._memory_snapshot", side_effect=RuntimeError("boom")):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["memory"] == {"error": "RuntimeError"}


# ---------------------------------------------------------------------------
# /api/rum
# ---------------------------------------------------------------------------

import routers.observability as obs  # noqa: E402

FULL_RUM = {
    "phase": "load",
    "page": "/",
    "device": "kiosk-03",
    "seq": 1,
    "visible_ms": 10500,
    "ttfb_ms": 120,
    "dom_content_loaded_ms": 900,
    "load_ms": 2100,
    "transfer_kb": 14.2,
    "fcp_ms": 800,
    "lcp_ms": 1900,
    "cls": 0.012,
    "inp_ms": 96,
    "longtask_count": 7,
    "longtask_total_ms": 820,
    "longtask_max_ms": 310,
    "resource_count": 23,
    "resource_transfer_kb": 812.5,
    "resources": [
        {"host": "cdn.tailwindcss.com", "path": "/", "initiator": "script",
         "duration_ms": 1400, "transfer_kb": 110.3},
        {"host": "cdn.jsdelivr.net", "path": "/npm/@mediapipe/face_detection/face_detection.js",
         "initiator": "script", "duration_ms": 900, "transfer_kb": 40},
    ],
    "device_memory_gb": 4,
    "cpu_cores": 8,
    "effective_type": "4g",
    "downlink_mbps": 3.5,
    "rtt_ms": 150,
    "save_data": False,
    "viewport": "412x915",
    "dpr": 2.625,
    "user_agent": "Mozilla/5.0 (Linux; Android 13)",
    "js_heap_used_mb": 38.1,
    "js_heap_limit_mb": 2048,
    "some_future_field": "diabaikan",
}


def _post_rum(payload, headers=None):
    with patch("routers.observability._insert_client_perf") as mock_insert, \
         patch("routers.observability.capture_event") as mock_capture:
        response = client.post("/api/rum", json=payload, headers=headers or {})
    return response, mock_insert, mock_capture


def test_rum_accepts_full_payload_and_persists():
    obs._slow_alerted_at.clear()
    response, mock_insert, mock_capture = _post_rum(FULL_RUM)
    assert response.status_code == 202
    assert response.json() == {"status": "received"}
    row = mock_insert.call_args.args[0]
    assert row["device"] == "kiosk-03"
    assert row["phase"] == "load"
    assert row["lcp_ms"] == 1900
    assert row["resources"][0]["host"] == "cdn.tailwindcss.com"
    assert row["extra"] == {"seq": 1}
    assert "some_future_field" not in row and "some_future_field" not in row["extra"]
    mock_capture.assert_not_called()  # halaman normal tidak masuk Sentry


def test_rum_clamps_absurd_values():
    """Bug jam di satu browser tidak boleh membuang seluruh snapshot."""
    payload = {
        "phase": "periodic",
        "lcp_ms": 1e15,
        "cls": -3,
        "cpu_cores": "banyak",
        "page": "/" + "x" * 5000,
        "resources": [{"host": "h", "path": "/p" * 200, "duration_ms": 5}] * 20,
    }
    response, mock_insert, _ = _post_rum(payload)
    assert response.status_code == 202
    row = mock_insert.call_args.args[0]
    assert row["lcp_ms"] == obs.TEN_MINUTES_MS
    assert "cls" not in row and "cpu_cores" not in row
    assert len(row["page"]) == 300
    assert len(row["resources"]) == 6
    assert len(row["resources"][0]["path"]) == 80


def test_rum_rejects_unknown_phase():
    response, mock_insert, _ = _post_rum({"phase": "hack"})
    assert response.status_code == 422
    mock_insert.assert_not_called()


def test_rum_still_202_when_insert_fails():
    """Tabel belum dimigrasi tidak boleh membuat browser melihat error."""
    obs._insert_warned = False
    with patch("routers.observability._insert_client_perf", side_effect=RuntimeError("no table")), \
         patch.object(obs.rum_logger, "warning") as mock_warn:
        first = client.post("/api/rum", json={"phase": "load"})
        second = client.post("/api/rum", json={"phase": "load"})
    assert first.status_code == 202 and second.status_code == 202
    assert mock_warn.call_count == 1  # peringatan sekali per proses, bukan per snapshot


def test_rum_device_falls_back_to_header_and_is_sanitized():
    payload = {k: v for k, v in FULL_RUM.items() if k != "device"}
    response, mock_insert, _ = _post_rum(payload, headers={"X-KP-Device": "Kiosk_07<script>"})
    assert response.status_code == 202
    assert mock_insert.call_args.args[0]["device"] == "kiosk-07script"


def test_rum_body_device_wins_over_header():
    response, mock_insert, _ = _post_rum(FULL_RUM, headers={"X-KP-Device": "kiosk-99"})
    assert mock_insert.call_args.args[0]["device"] == "kiosk-03"


def test_rum_slow_load_goes_to_sentry_once_per_device_per_hour():
    obs._slow_alerted_at.clear()
    slow = dict(FULL_RUM, device="kiosk-slow", lcp_ms=9000)
    _, _, first_capture = _post_rum(slow)
    _, _, second_capture = _post_rum(slow)
    assert first_capture.call_count == 1
    assert first_capture.call_args.kwargs["level"] == "info"
    assert second_capture.call_count == 0
    # Snapshot periodik yang lambat tidak memicu Sentry.
    obs._slow_alerted_at.clear()
    _, _, periodic_capture = _post_rum(dict(slow, phase="periodic"))
    assert periodic_capture.call_count == 0
