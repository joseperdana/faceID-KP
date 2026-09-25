"""Penjaga regresi: tidak boleh ada I/O database di thread event loop.

Insiden Gibbor (19 Sep 2026): proses uvicorn tidak mati, tapi membeku. Beberapa
handler `async def` memanggil supabase-py (sinkron) langsung di event loop,
sehingga setiap round-trip ke Supabase menahan SEMUA request lain di proses —
sampai halaman `/` dan file /static ikut 504 di nginx.

Cara kerja tes ini: klien HTTP Supabase diganti MockTransport yang mencatat,
untuk setiap request ke Supabase, apakah ia dikirim dari thread event loop.
`asyncio.get_running_loop()` hanya berhasil di thread yang menjalankan loop;
di thread threadpool ia melempar RuntimeError. Lalu SETIAP rute di `app.routes`
dipanggil lewat TestClient. Rute baru tanpa resep di RECIPES membuat tes gagal,
jadi handler baru tidak bisa lolos tanpa ikut diperiksa.

Seluruh jalur asli ikut teruji — DBService -> supabase-py -> postgrest ->
httpx (RetryingClient) — hanya jaringannya yang palsu.
"""
import asyncio
import io
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import database
from core import flags
from core.flags import _refresh as _real_flags_refresh  # diambil sebelum conftest mem-patch-nya
from core.security import COOKIE_NAME, create_access_token
from main import app
from services.db_service import DBService


def _on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


@dataclass
class DbCall:
    method: str
    path: str
    on_loop: bool
    thread: str


@dataclass
class FakeSupabase:
    calls: List[DbCall] = field(default_factory=list)
    # Hasil rpc/match_faces. Kosong = wajah baru (jalur register lengkap);
    # berisi = wajah dikenal (jalur recognize lengkap).
    match_result: list = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def handler(self, request: httpx.Request) -> httpx.Response:
        with self.lock:
            self.calls.append(DbCall(
                request.method, request.url.path, _on_event_loop(), threading.current_thread().name,
            ))
        path = request.url.path
        query = str(request.url.query)
        if "/rpc/" in path:
            body = self.match_result
        elif request.method == "POST":
            body = [{"id": 1, "user_id": 1}]
        elif request.method == "GET" and path.endswith("/users") and "name_key" not in query:
            # Satu anggota supaya manual-checkin / update-face berjalan sampai insert.
            body = [{"id": 1, "full_name": "Anggota Uji", "gender": "Pria",
                     "phone_number": "081234567890", "attendance_logs": []}]
        else:
            body = []
        return httpx.Response(200, json=body, headers={"Content-Range": "0-0/0"})

    def on_loop_calls(self) -> List[DbCall]:
        return [c for c in self.calls if c.on_loop]


@pytest.fixture(autouse=True)
def no_sentry_delivery():
    import sentry_sdk
    with patch.object(sentry_sdk.get_client(), "capture_event", return_value=None):
        yield


@pytest.fixture
def fake_db(monkeypatch, tmp_path):
    fake = FakeSupabase()
    fake_client = database.build_http_client(transport=httpx.MockTransport(fake.handler))
    old_postgrest = database.supabase._postgrest
    monkeypatch.setattr(database.supabase.options, "httpx_client", fake_client)
    database.supabase._postgrest = None  # dibuat ulang dengan klien palsu
    assert database.supabase.postgrest.session is fake_client, "Supabase masih memakai jaringan sungguhan"

    # conftest mengunci saklar ke nilai bawaan tanpa menyentuh database. Di sini
    # justru jalur database-nya yang ingin diperiksa, jadi _refresh asli dipulihkan.
    monkeypatch.setattr(flags, "_refresh", _real_flags_refresh)
    flags._cache = {}
    flags._cached_at = 0.0

    # Upload photobooth jangan sampai menulis ke frontend/uploads sungguhan.
    monkeypatch.setattr("routers.photobooth.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("face_service.face_service.get_embedding", lambda _content: [0.1] * 512)

    yield fake

    # Tunggu penyegaran saklar di latar selesai sebelum klien asli dipulihkan,
    # supaya thread susulan tidak menembak Supabase sungguhan.
    with flags._refresh_lock:
        pass
    database.supabase._postgrest = old_postgrest
    flags._cache = {}
    flags._cached_at = 0.0


def _admin_cookies() -> Dict[str, str]:
    return {COOKIE_NAME: create_access_token({"sub": "admin"})}


def _photo(name="files"):
    return (name, ("f.jpg", io.BytesIO(b"bukan-jpeg-sungguhan"), "image/jpeg"))


@dataclass
class Recipe:
    kwargs: Callable[[], dict] = dict
    admin: bool = False
    match_result: Optional[list] = None


KNOWN_FACE = [{"id": 1, "full_name": "Anggota Uji", "similarity": 0.9}]

# (METHOD, template path) -> cara memanggilnya dengan input minimal yang sah.
RECIPES: Dict[tuple, Recipe] = {
    ("GET", "/"): Recipe(),
    ("GET", "/photobooth"): Recipe(),
    ("GET", "/login"): Recipe(),
    ("GET", "/register"): Recipe(admin=True),
    ("GET", "/dashboard"): Recipe(admin=True),
    ("GET", "/logout"): Recipe(),
    ("GET", "/diagrams/architecture"): Recipe(),
    ("GET", "/diagrams/lifecycle"): Recipe(),
    ("GET", "/diagrams/workflow"): Recipe(),
    ("POST", "/api/login"): Recipe(lambda: {"json": {"password": "salah-sengaja"}}),
    ("POST", "/api/recognize"): Recipe(
        lambda: {"files": [_photo("file")]}, match_result=KNOWN_FACE),
    ("GET", "/api/users/search"): Recipe(lambda: {"params": {"q": "an"}}),
    ("POST", "/api/attendance/manual-checkin"): Recipe(lambda: {"data": {"user_id": "1"}}),
    ("POST", "/api/register"): Recipe(lambda: {
        "data": {"full_name": "Pendaftar Uji", "gender": "Pria", "phone_number": "081234567890"},
        "files": [_photo(), _photo(), _photo()],
    }),
    ("POST", "/api/update-face"): Recipe(lambda: {
        "data": {"full_name": "Anggota Uji"}, "files": [_photo(), _photo(), _photo()],
    }),
    ("GET", "/api/users"): Recipe(admin=True),
    ("GET", "/api/users/{user_id}/history"): Recipe(admin=True),
    ("PUT", "/api/users/{user_id}"): Recipe(lambda: {
        "json": {"full_name": "Anggota Uji", "gender": "Pria", "phone_number": "081234567890"},
    }, admin=True),
    ("DELETE", "/api/users/{user_id}"): Recipe(admin=True),
    ("GET", "/api/dashboard-stats"): Recipe(admin=True),
    ("GET", "/api/analytics"): Recipe(admin=True),
    ("GET", "/api/export-excel"): Recipe(admin=True),
    ("GET", "/api/export-excel/date/{target_date}"): Recipe(admin=True),
    ("GET", "/api/attendance/date/{target_date}"): Recipe(admin=True),
    ("DELETE", "/api/logs/{log_id}"): Recipe(admin=True),
    ("GET", "/api/all-logs"): Recipe(admin=True),
    ("POST", "/api/photobooth/upload"): Recipe(lambda: {
        "json": {"image": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="},
    }),
    ("GET", "/p/{photo_id}"): Recipe(),
    ("GET", "/health"): Recipe(),
    ("POST", "/api/client-error"): Recipe(lambda: {"json": {"message": "uji"}}),
    ("POST", "/api/rum"): Recipe(lambda: {"json": {"phase": "load", "page": "/"}}),
    ("GET", "/api/flags"): Recipe(),
    ("GET", "/api/flags/detail"): Recipe(admin=True),
    ("PUT", "/api/flags/{key}"): Recipe(lambda: {"json": {"enabled": True}}, admin=True),
}

PATH_PARAMS = {
    "user_id": "1", "target_date": "2026-09-19", "log_id": "1",
    "photo_id": "tidakada", "key": "photobooth",
}


def _app_routes():
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                yield method, route.path


def test_every_route_has_a_recipe():
    """Rute baru wajib ditambahkan ke RECIPES supaya ikut diperiksa di bawah."""
    missing = sorted(set(_app_routes()) - set(RECIPES))
    assert not missing, f"Tambahkan resep untuk rute baru ini di RECIPES: {missing}"
    stale = sorted(set(RECIPES) - set(_app_routes()))
    assert not stale, f"Resep untuk rute yang sudah tidak ada: {stale}"


@pytest.mark.parametrize("method, path", sorted(RECIPES))
def test_route_never_touches_database_on_event_loop(fake_db, method, path):
    recipe = RECIPES[(method, path)]
    fake_db.match_result = recipe.match_result or []
    url = path.format(**PATH_PARAMS)
    with TestClient(app) as c:
        if recipe.admin:
            for k, v in _admin_cookies().items():
                c.cookies.set(k, v)
        res = c.request(method, url, follow_redirects=False, **recipe.kwargs())

    # 401/405/422 berarti isi handler tidak pernah jalan — resepnya yang salah,
    # dan tes ini jadi tidak memeriksa apa-apa. Login yang salah memang 401.
    if (method, path) != ("POST", "/api/login"):
        assert res.status_code not in (401, 405, 422), (res.status_code, res.text[:300])

    offenders = fake_db.on_loop_calls()
    assert not offenders, (
        f"{method} {path} memanggil Supabase di thread event loop: "
        f"{[(c.method, c.path) for c in offenders]}. Bungkus dengan run_in_threadpool "
        f"atau jadikan handlernya `def`."
    )


def test_database_heavy_routes_really_reach_the_fake(fake_db):
    """Pastikan pemeriksaan di atas tidak lolos hanya karena tak ada query sama sekali."""
    with TestClient(app) as c:
        c.cookies.set(COOKIE_NAME, create_access_token({"sub": "admin"}))
        c.post("/api/register", data={
            "full_name": "Pendaftar Uji", "gender": "Pria", "phone_number": "081234567890",
        }, files=[_photo(), _photo(), _photo()])
    paths = {(c.method, c.path.rsplit("/", 1)[-1]) for c in fake_db.calls}
    # nama kembar, wajah kembar, profil Lark, insert anggota, insert absensi
    assert ("GET", "users") in paths
    assert ("POST", "match_faces") in paths
    assert ("GET", "lark_directory") in paths
    assert ("POST", "users") in paths
    assert ("POST", "attendance_logs") in paths
    assert not fake_db.on_loop_calls()


def test_guard_detects_blocking_call(fake_db):
    """Tes ini sendiri harus bisa gagal: handler async yang memanggil DBService
    langsung (pola sebelum perbaikan) wajib tertangkap sebagai panggilan di loop."""
    bad = FastAPI()

    @bad.get("/bad")
    async def blocking_handler():
        return DBService.get_all_users()

    with TestClient(bad) as c:
        assert c.get("/bad").status_code == 200
    assert fake_db.on_loop_calls(), "Penjaga tidak mendeteksi query di event loop"


def test_flags_never_query_database_on_event_loop(fake_db):
    """is_enabled() dipanggil dari handler async (geofence, Lark, registrasi).
    Cache kosong/basi tidak boleh membuatnya menunggu database di loop."""
    async def call_from_loop():
        return flags.is_enabled("geofence"), flags.all_flags()

    geofence, values = asyncio.run(call_from_loop())
    assert geofence == flags._defaults()["geofence"]
    assert set(values) == set(flags.FLAGS)
    with flags._refresh_lock:  # tunggu penyegaran latar
        pass
    assert fake_db.calls, "penyegaran di latar seharusnya tetap membaca tabel"
    assert not fake_db.on_loop_calls()
