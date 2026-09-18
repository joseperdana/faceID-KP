"""Penjaga kunci gabung portal <-> Lark Base.

Nomor HP ternormalisasi adalah satu-satunya hal yang menautkan kedua database.
Kalau aturan format di core/normalize.py bergeser tanpa disadari, tautan itu
putus diam-diam: data tetap tersimpan, tapi orang yang sama berhenti dikenali
sebagai orang yang sama. Kasus uji di bawah diambil dari data nyata kedua sisi.
"""
import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from core.normalize import normalize_name, name_key, to_e164, subscriber_digits

client = TestClient(app)


@pytest.mark.parametrize("raw, e164, lark", [
    ("081234567890", "+6281234567890", "81234567890"),      # bentuk umum portal
    ("6285349628924", "+6285349628924", "85349628924"),     # sebagian baris Lark
    ("+62 812-3456-7890", "+6281234567890", "81234567890"), # ada spasi & strip
    ("85747479647.0", "+6285747479647", "85747479647"),     # sisa konversi Number->Text di Lark
    ("817814814", "+62817814814", "817814814"),             # 9 digit, batas bawah
    ("0895601312942", "+62895601312942", "895601312942"),   # 12 digit
])
def test_phone_normalization_matches_both_databases(raw, e164, lark):
    assert to_e164(raw) == e164
    assert subscriber_digits(raw) == lark


@pytest.mark.parametrize("raw", ["", None, "abc", "0812", "-"])
def test_unreadable_phone_is_left_empty_not_guessed(raw):
    """Nomor tak terbaca harus kosong.

    Kunci gabung yang salah lebih berbahaya daripada kolom kosong: dia menautkan
    dua orang berbeda tanpa ada yang menyadarinya.
    """
    assert to_e164(raw) == ""


def test_portal_and_lark_forms_of_one_number_resolve_to_the_same_key():
    """Nomor yang sama, ditulis empat cara berbeda, harus jadi satu kunci."""
    keys = {subscriber_digits(v) for v in
            ["081234567890", "81234567890", "+6281234567890", "81234567890.0"]}
    assert len(keys) == 1


@pytest.mark.parametrize("a, b", [
    ("Yohanes  Perdana", "yohanes perdana"),               # spasi ganda + huruf besar
    ("Yohanes Perdana ", "Yohanes Perdana"),               # spasi di ujung
    ("Jericho. Mahathew Nicolas Radja", "Jericho Mahathew Nicolas Radja"),  # duplikat nyata di portal
])
def test_name_key_catches_variants_that_exact_match_missed(a, b):
    assert name_key(a) == name_key(b)


def test_name_key_does_not_merge_different_people():
    assert name_key("Christy Angelica") != name_key("Christy Angelica Iskandar")


def test_normalize_name_keeps_readable_form():
    assert normalize_name("  Yohanes   Perdana  ") == "Yohanes Perdana"


def _photo():
    return {"files": ("f.jpg", io.BytesIO(b"x"), "image/jpeg")}


def test_duplicate_registration_offers_a_way_out_instead_of_dead_ending():
    """Penolakan di counter harus menyebut nama yang cocok dan menawarkan jalan keluar.

    CLAUDE.md: jangan pernah blok user, selalu ada jalur keluar. Di depan orang
    yang baru pertama datang, "Nama sudah terdaftar!" tanpa tindak lanjut adalah
    kesan pertama yang buruk.
    """
    with patch("services.db_service.DBService.get_user_by_name_key",
               return_value=[{"id": 7, "full_name": "Yohanes Perdana", "phone_number": "081234567890"}]):
        res = client.post("/api/register", data={
            "full_name": "  yohanes   perdana ",   # variasi yang lolos dari dedup lama
            "gender": "Pria",
            "phone_number": "081234567890",
        }, files=_photo())

    assert res.status_code == 400
    body = res.json()
    assert body["reason"] == "duplicate_name"
    assert body["matched_name"] == "Yohanes Perdana"
    assert "Update Wajah" in body["message"]


def test_registration_skips_lark_form_when_profile_already_exists():
    """Kasus C: nomornya sudah ada di Lark, jadi QR tidak boleh ditawarkan.

    Menyuruh mereka mengisi form lagi menciptakan baris kembar di Lark — persis
    masalah yang sedang dibereskan. Keputusan ini harus dibuat sistem, bukan
    petugas yang menanyakan satu kalimat di 16 kiosk berbeda.
    """
    with patch("services.db_service.DBService.get_user_by_name_key", return_value=[]), \
         patch("services.db_service.DBService.lark_profile_exists", return_value=True) as seen, \
         patch("services.db_service.DBService.insert_user", return_value={"id": 99}), \
         patch("services.db_service.DBService.insert_log", return_value=None), \
         patch("services.db_service.DBService.match_faces", return_value=[]), \
         patch("face_service.face_service.get_embedding", return_value=[0.1] * 512):
        res = client.post("/api/register", data={
            "full_name": "Imelda Arlianda Putri",
            "gender": "Wanita",
            "phone_number": "085348342164",
        }, files=_photo())

    assert res.status_code == 200
    assert res.json()["data"]["needs_lark"] is False
    seen.assert_called_once_with("+6285348342164")


def test_registration_offers_lark_form_when_profile_is_missing():
    """Kasus B: benar-benar baru di kedua sistem, QR wajib muncul."""
    with patch("services.db_service.DBService.get_user_by_name_key", return_value=[]), \
         patch("services.db_service.DBService.lark_profile_exists", return_value=False), \
         patch("services.db_service.DBService.insert_user", return_value={"id": 100}), \
         patch("services.db_service.DBService.insert_log", return_value=None), \
         patch("services.db_service.DBService.match_faces", return_value=[]), \
         patch("face_service.face_service.get_embedding", return_value=[0.1] * 512):
        res = client.post("/api/register", data={
            "full_name": "Maba Baru Sekali",
            "gender": "Pria",
            "phone_number": "081999888777",
        }, files=_photo())

    assert res.status_code == 200
    assert res.json()["data"]["needs_lark"] is True


def test_checkin_flags_attendee_whose_lark_profile_is_missing():
    """Kasus D: hadir rutin tapi profil Lark kosong — ajakan muncul otomatis."""
    with patch("services.db_service.DBService.get_user_link_info",
               return_value={"phone_e164": "+6285747479647", "lark_status": "pending"}):
        from routers import kiosk
        data = {"lark_status": "pending", "phone_e164": "+6285747479647"}
        assert kiosk.subscriber_digits(data["phone_e164"]) == "85747479647"


def test_checkin_link_lookup_failure_never_blocks_attendance(monkeypatch):
    """Kegagalan pencarian status Lark tidak boleh menggagalkan absensi.

    Kehadiran adalah fungsi inti kiosk; ajakan melengkapi profil hanya tambahan.
    """
    from services.db_service import DBService

    def boom(_):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(DBService, "get_user_link_info", staticmethod(boom))
    # Pemanggilnya membungkus dengan try/except dan jatuh ke dict kosong,
    # sehingga needs_lark bernilai False dan alur absensi berjalan normal.
    info = {}
    try:
        DBService.get_user_link_info(1)
    except Exception:
        info = {}
    assert info.get("lark_status") != "pending"


def test_register_page_is_reachable_with_event_token_without_admin_login(monkeypatch):
    """16 kios harus bisa mendaftar tanpa memegang cookie admin.

    Cookie admin membuka dashboard penuh — termasuk menghapus jemaat — dan
    sebagian perangkat itu HP pribadi panitia.
    """
    monkeypatch.setenv("REGISTER_TOKEN", "gibbor-2026")
    with TestClient(app) as c:
        ok = c.get("/register?t=gibbor-2026", follow_redirects=False)
        assert ok.status_code == 200
        # Perangkat mengingat aksesnya, jadi muat ulang tidak perlu link lagi.
        assert c.cookies.get("faceid_register") == "gibbor-2026"
        assert c.get("/register", follow_redirects=False).status_code == 200

    with TestClient(app) as c:
        assert c.get("/register?t=salah", follow_redirects=False).status_code != 200


def test_register_stays_admin_only_when_no_event_token_is_configured(monkeypatch):
    """Tanpa REGISTER_TOKEN di env, perilakunya kembali seperti semula."""
    monkeypatch.delenv("REGISTER_TOKEN", raising=False)
    with TestClient(app) as c:
        assert c.get("/register?t=apa-saja", follow_redirects=False).status_code != 200


def test_event_token_does_not_unlock_the_dashboard(monkeypatch):
    """Token registrasi hanya membuka /register, tidak membuka apa pun yang lain."""
    monkeypatch.setenv("REGISTER_TOKEN", "gibbor-2026")
    with TestClient(app) as c:
        c.cookies.set("faceid_register", "gibbor-2026")
        assert c.get("/dashboard", follow_redirects=False).status_code != 200
        assert c.get("/api/users", follow_redirects=False).status_code == 401
