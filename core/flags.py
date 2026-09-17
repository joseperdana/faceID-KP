"""Saklar fitur yang bisa diubah pengurus dari dashboard, tanpa deploy.

Yang masuk ke sini hanyalah fitur yang nilai benarnya berubah menurut ACARA,
bukan menurut lingkungan deploy: geofence benar saat ibadah reguler dan salah
saat retret di luar kota, Lark benar saat Gibbor dan salah di Sabtu biasa.
Konfigurasi yang tidak pernah berubah antar acara tetap di .env.

Dua aturan yang menjaga kiosk tetap hidup:

1. Kegagalan membaca flag TIDAK PERNAH mematikan fitur. Kalau tabelnya tak
   terbaca, nilainya jatuh ke bawaan — yaitu perilaku yang berlaku hari ini.
   Kita menambah ketergantungan baru ke jalur absensi; ketergantungan itu tidak
   boleh punya kuasa menghentikan antrian.
2. Tidak ada query database per pemindaian wajah. Nilainya disimpan di memori
   proses selama CACHE_TTL detik. Konsekuensinya saklar butuh sampai setengah
   menit untuk terasa di semua kiosk — jauh lebih murah daripada satu round-trip
   untuk setiap wajah yang lewat.
"""
import os
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
    _cache = values
    _cached_at = time.time()
    return values


def all_flags(force: bool = False) -> Dict[str, bool]:
    if force or not _cache or (time.time() - _cached_at) > CACHE_TTL_SECONDS:
        return _refresh()
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
