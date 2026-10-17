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


def test_photo_page_rejects_ids_that_are_not_generated_ids(tmp_path, monkeypatch):
    """ID foto selalu 8 karakter heksadesimal (uuid4().hex[:8]).

    Apa pun selain itu ditolak sebelum menyentuh sistem berkas atau HTML:
    CodeQL menandai /p/{photo_id} sebagai path injection dan reflective XSS
    karena nilai dari URL dipakai untuk menyusun path dan disisipkan ke HTML.
    Tes ini menanam berkas bernama berbahaya untuk membuktikan bahwa validasi,
    bukan kebetulan berkasnya tidak ada, yang menghentikan permintaan.
    """
    from routers import photobooth
    monkeypatch.setattr(photobooth, "UPLOAD_DIR", tmp_path)
    evil = 'x"><img src=x onerror=alert(1)>'
    (tmp_path / f"{evil}.jpg").write_bytes(b"jpg")
    (tmp_path / "...jpg").write_bytes(b"jpg")

    # "/p/.." tidak diuji: klien HTTP menormalkannya jadi "/" sebelum dikirim.
    for bad in (evil, "...", "ABCDEF12", "abc", "abcdef123"):
        res = client.get(f"/p/{bad}")
        assert res.status_code == 404, bad
        assert "onerror=alert(1)" not in res.text

    (tmp_path / "a1b2c3d4.jpg").write_bytes(b"jpg")
    assert client.get("/p/a1b2c3d4").status_code == 200
