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
