import pytest
import base64
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# 1x1 white pixel JPEG base64 string
SAMPLE_JPEG_BASE64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
SAMPLE_GIF_BASE64 = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

def test_photobooth_upload_success():
    payload = {
        "image": SAMPLE_JPEG_BASE64,
        "gif_image": SAMPLE_GIF_BASE64,
        "frame": "3-strip",
        "caption": "KP Bromo Nusantara Test"
    }
    response = client.post("/api/photobooth/upload", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "photo_id" in data
    assert data["view_url"].startswith("/p/")
    assert data["download_url"].startswith("/static/uploads/photobooth/")
    assert data["gif_download_url"].endswith(".gif")
    assert "qr_url" in data

    # Test GET /p/{photo_id}
    photo_id = data["photo_id"]
    get_res = client.get(f"/p/{photo_id}")
    assert get_res.status_code == 200
    assert "KP45 Photo Strip" in get_res.text
    assert photo_id in get_res.text

def test_photobooth_view_not_found():
    response = client.get("/p/nonexistent999")
    assert response.status_code == 404
    assert "Foto Tidak Ditemukan" in response.text
