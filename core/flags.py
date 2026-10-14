"""Saklar fitur yang bisa diubah pengurus dari dashboard, tanpa deploy.

Yang masuk ke sini hanyalah fitur yang nilai benarnya berubah menurut ACARA,
bukan menurut lingkungan deploy: geofence benar saat ibadah reguler dan salah
saat retret di luar kota, Lark benar saat Gibbor dan salah di Sabtu biasa.
Konfigurasi yang tidak pernah berubah antar acara tetap di .env.

Dua aturan yang menjaga kiosk tetap hidup:

1. Kegagalan membaca flag TIDAK PERNAH mematikan fitur. Kalau tabelnya tak
   terbaca, nilainya tetap nilai terakhir yang berhasil dibaca, atau bawaan
   (perilaku sebelum saklar ada) kalau belum pernah terbaca sama sekali.
   Kita menambah ketergantungan baru ke jalur absensi; ketergantungan itu tidak
   boleh punya kuasa menghentikan antrian.
2. Tidak ada query database per pemindaian wajah. Nilainya disimpan di memori
   proses selama CACHE_TTL detik. Konsekuensinya saklar butuh sampai setengah
   menit untuk terasa di semua kiosk — jauh lebih murah daripada satu round-trip
   untuk setiap wajah yang lewat.
3. Tidak pernah ada I/O jaringan di thread event loop. Saat Gibbor, cache yang
   kedaluwarsa membuat is_enabled() menjalankan query Supabase langsung di
   event loop — seluruh proses (termasuk halaman `/`) ikut membeku selama
   query itu. Kalau pemanggilnya event loop, nilai cache (atau bawaan, kalau
   cache masih kosong) langsung dikembalikan dan penyegaran jalan di thread
   terpisah (stale-while-revalidate). Pemanggil dari thread pekerja (handler
   `def`, run_in_threadpool) tetap menyegarkan secara sinkron seperti dulu,
   karena yang tertahan hanya thread itu sendiri. Cache juga dihangatkan saat
   startup (lihat main.py), jadi nilai bawaan hanya terpakai di milidetik
   pertama setelah proses hidup — atau saat tabelnya memang tak terbaca.
"""
import asyncio
import os
import threading
import time
from typing import Dict

from core.observability import capture_error

CACHE_TTL_SECONDS = 30


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("true", "1", "yes")


def _default_geofence() -> bool:
    # Bawaannya tetap dari .env supaya men-deploy fitur ini tidak mengubah
    # perilaku apa pun sampai ada yang benar-benar menggeser saklarnya.
    return _env_bool("ENABLE_GEOFENCE")


# key -> (label untuk dashboard, fungsi nilai bawaan, penjelasan)
FLAGS = {
    "geofence": (
        "Geofence Absensi",
        _default_geofence,
        "Tolak absensi dari luar radius 200m gereja. Matikan saat ibadah di luar lokasi.",
    ),
    "lark_handoff": (
        "Pengisian Data Lark",
        lambda: True,
        "Arahkan ke form Lark setelah daftar atau absen. Matikan di luar acara besar.",
    ),
    "photobooth": (
        "KP45 Photobooth",
        lambda: True,
        "Tampilkan dan buka halaman photobooth. Matikan di luar acara khusus.",
    ),
    "registration": (
        "Pendaftaran Wajah",
        lambda: True,
        "Izinkan pendaftaran anggota baru. Matikan untuk menutup pendaftaran tanpa mematikan absensi.",
    ),
}

_cache: Dict[str, bool] = {}
_cached_at: float = 0.0


def _defaults() -> Dict[str, bool]:
    return {k: meta[1]() for k, meta in FLAGS.items()}


def _refresh() -> Dict[str, bool]:
    global _cache, _cached_at
    values = _defaults()
    try:
        from database import supabase
        rows = supabase.table("feature_flags").select("key, enabled").execute().data
        for r in rows:
            if r["key"] in FLAGS:
                values[r["key"]] = bool(r["enabled"])
    except Exception as e:
        # Sengaja tidak di-raise: nilai bawaan sudah siap, dan absensi lebih
        # penting daripada ketepatan saklar.
        capture_error(e, where="flags.refresh")
        # Nilai terakhir yang berhasil dibaca lebih benar daripada bawaan .env:
        # kalau geofence sengaja dimatikan untuk retret, gangguan Supabase
        # sesaat tidak boleh tiba-tiba menyalakannya dan menolak semua scan.
        if _cache:
            values = dict(_cache)
    _cache = values
    _cached_at = time.time()
    return values


# Satu penyegaran dalam satu waktu. Saat TTL habis di tengah antrian, puluhan
# scan bisa melihat cache basi bersamaan; cukup satu yang bertanya ke database,
# sisanya memakai nilai lama yang hanya terlambat beberapa detik.
_refresh_lock = threading.Lock()


def _stale() -> bool:
    return not _cache or (time.time() - _cached_at) > CACHE_TTL_SECONDS


def _on_event_loop() -> bool:
    # get_running_loop() hanya berhasil di thread yang sedang menjalankan event
    # loop; di thread threadpool ia melempar RuntimeError.
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _served() -> Dict[str, bool]:
    return dict(_cache) if _cache else _defaults()


def _refresh_in_background() -> None:
    if not _refresh_lock.acquire(blocking=False):
        return
    # Fungsinya diambil sekarang, bukan saat thread berjalan, supaya patch tes
    # yang sudah dilepas tidak membuat thread susulan menembak database asli.
    refresh = _refresh

    def run():
        try:
            refresh()
        finally:
            _refresh_lock.release()

    try:
        threading.Thread(target=run, name="flags-refresh", daemon=True).start()
    except Exception as e:
        _refresh_lock.release()
        capture_error(e, where="flags.refresh_in_background")


def warm_up() -> None:
    """Mulai isi cache tanpa menunggu hasilnya. Dipanggil saat startup."""
    _refresh_in_background()


def all_flags(force: bool = False) -> Dict[str, bool]:
    if _on_event_loop():
        if force or _stale():
            _refresh_in_background()
        return _served()
    if force or _stale():
        # Kalau thread lain sedang menyegarkan, jangan antre di belakangnya:
        # nilai lama (atau bawaan) sudah cukup baik untuk permintaan ini.
        if not _refresh_lock.acquire(blocking=False):
            return _served()
        try:
            return _refresh()
        finally:
            _refresh_lock.release()
    return dict(_cache)


def is_enabled(key: str) -> bool:
    if key not in FLAGS:
        return False
    try:
        return all_flags()[key]
    except Exception as e:
        capture_error(e, where="flags.is_enabled", key=key)
        return FLAGS[key][1]()


def set_flag(key: str, enabled: bool) -> bool:
    """Simpan nilai baru dan segarkan cache proses ini seketika."""
    if key not in FLAGS:
        raise KeyError(key)
    from database import supabase
    supabase.table("feature_flags").upsert(
        {"key": key, "enabled": bool(enabled)}, on_conflict="key"
    ).execute()
    # Tunggu penyegaran latar yang mungkin sedang jalan: kalau ia mulai sebelum
    # upsert dan selesai sesudahnya, nilai lamanya akan menimpa nilai baru.
    with _refresh_lock:
        _refresh()
    return bool(enabled)


def describe() -> list:
    """Bentuk yang dipakai dashboard: label, penjelasan, dan nilai berlakunya."""
    values = all_flags()
    return [
        {
            "key": key,
            "label": meta[0],
            "description": meta[2],
            "enabled": values.get(key, meta[1]()),
        }
        for key, meta in FLAGS.items()
    ]
