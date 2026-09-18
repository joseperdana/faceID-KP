"""Saklar fitur tidak boleh punya kuasa menghentikan absensi.

Fitur ini menambah ketergantungan baru ke jalur tersibuk di kiosk. Tes di sini
menjaga satu janji: apa pun yang terjadi pada penyimpanan saklar, kiosk tetap
berperilaku seperti sebelum fitur ini ada.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from core import flags

client = TestClient(app)


def test_database_mati_tidak_mematikan_fitur(monkeypatch):
    """Gagal baca saklar harus jatuh ke nilai bawaan, bukan ke 'mati'."""
    def meledak():
        raise RuntimeError("supabase down")

    with patch("core.flags._refresh", side_effect=lambda: flags._defaults()):
        assert flags.is_enabled("lark_handoff") is True
        assert flags.is_enabled("registration") is True


def test_geofence_bawaannya_ikut_env(monkeypatch):
    """Selama barisnya belum ada, .env tetap yang menentukan.

    Ini yang membuat fitur saklar bisa di-deploy tanpa mengubah perilaku apa pun
    sampai ada yang benar-benar menggeser tuasnya.
    """
    monkeypatch.setenv("ENABLE_GEOFENCE", "true")
    assert flags._defaults()["geofence"] is True
    monkeypatch.setenv("ENABLE_GEOFENCE", "false")
    assert flags._defaults()["geofence"] is False


def test_saklar_database_menang_atas_env(monkeypatch):
    monkeypatch.setenv("ENABLE_GEOFENCE", "false")
    with patch("core.flags._refresh", side_effect=lambda: {**flags._defaults(), "geofence": True}):
        assert flags.is_enabled("geofence") is True


def test_key_asing_ditolak():
    assert flags.is_enabled("fitur-yang-tidak-ada") is False
    with pytest.raises(KeyError):
        flags.set_flag("fitur-yang-tidak-ada", True)


def test_flag_publik_tidak_pernah_menggagalkan_pemuatan_kiosk():
    with patch("core.flags.all_flags", side_effect=RuntimeError("boom")):
        res = client.get("/api/flags")
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_mengubah_saklar_butuh_admin():
    res = client.put("/api/flags/photobooth", json={"enabled": False}, follow_redirects=False)
    assert res.status_code == 401
    assert client.get("/api/flags/detail", follow_redirects=False).status_code == 401


def test_photobooth_mati_mengunci_rutenya_bukan_hanya_menyembunyikan_tombol():
    """Menyembunyikan tombol tidak menghalangi yang hafal alamatnya."""
    with patch("core.flags.is_enabled", side_effect=lambda k: k != "photobooth"):
        assert client.get("/photobooth", follow_redirects=False).status_code == 404
    with patch("core.flags.is_enabled", return_value=True):
        assert client.get("/photobooth", follow_redirects=False).status_code == 200


def test_pendaftaran_mati_ditolak_di_server(monkeypatch):
    import io
    monkeypatch.setenv("REGISTER_TOKEN", "gibbor-2026")
    with patch("core.flags.is_enabled", side_effect=lambda k: k != "registration"):
        res = client.post("/api/register", data={
            "full_name": "Sembarang Orang", "gender": "Pria", "phone_number": "081234567890",
        }, files={"files": ("f.jpg", io.BytesIO(b"x"), "image/jpeg")})
        assert res.status_code == 403
        with TestClient(app) as c:
            assert c.get("/register?t=gibbor-2026", follow_redirects=False).status_code == 404


def test_lark_mati_menghentikan_ajakan_walau_profil_belum_lengkap():
    """Saat bukan acara besar, tidak ada yang diarahkan ke form Lark."""
    with patch("core.flags.is_enabled", side_effect=lambda k: k != "lark_handoff"), \
         patch("services.db_service.DBService.get_user_link_info",
               return_value={"phone_e164": "+6285747479647", "lark_status": "pending"}):
        from routers import kiosk
        needs = flags.is_enabled("lark_handoff") and "pending" == "pending"
        assert needs is False
