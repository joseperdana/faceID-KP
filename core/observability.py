"""Helper observability — penangkapan error & event ke Sentry.

Kenapa modul ini ada:
Sebagian besar handler di `routers/` sengaja menangkap exception lalu me-return
JSONResponse 500 supaya pengguna kiosk tetap dapat pesan rapi dan tidak pernah
terblokir (prinsip "selalu ada jalur keluar 1-tap"). Efek sampingnya, exception
tidak pernah naik ke middleware sehingga integrasi Sentry tidak pernah melihatnya.

`capture_error()` menutup celah itu: perilaku ke pengguna tidak berubah sama
sekali, tapi errornya tetap terlapor. Semua fungsi di sini wajib fail-safe —
kegagalan observability tidak boleh menjatuhkan request absensi.
"""

import os
import sentry_sdk

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def resolve_release() -> str:
    """Tandai setiap event dengan commit yang sedang berjalan.

    Tanpa ini mustahil menjawab "error ini mulai muncul setelah deploy yang mana".
    Di VPS, RELEASE diisi script deploy; saat dev, dibaca dari git.
    """
    release = os.getenv("RELEASE")
    if release:
        return release
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, timeout=2
        ).decode().strip()
    except Exception:
        return "unknown"


RELEASE = resolve_release()


def _apply(scope, where, level, context):
    scope.set_tag("where", where)
    scope.level = level
    for key, value in context.items():
        scope.set_extra(key, value)


def capture_error(exc: BaseException, *, where: str, **context) -> None:
    """Laporkan exception yang sudah ditangani ke Sentry.

    Dipanggil tepat sebelum `return JSONResponse(500)` di handler. `where` adalah
    label ringkas lokasi kejadian (mis. "kiosk.recognize_face") supaya issue di
    dashboard bisa difilter tanpa membaca stack trace.
    """
    try:
        with sentry_sdk.new_scope() as scope:
            _apply(scope, where, "error", context)
            sentry_sdk.capture_exception(exc)
    except Exception:
        # Observability tidak boleh jadi sumber kegagalan baru.
        pass


def capture_event(message: str, *, where: str, level: str = "warning", **context) -> None:
    """Laporkan kejadian penting yang bukan exception.

    Contoh: wajah tidak lolos threshold, check-in ditolak geofence, error dari
    browser kiosk. Secara teknis bukan bug, tapi inilah yang selama ini hanya
    diketahui operator dan tidak pernah sampai ke siapa pun.
    """
    try:
        with sentry_sdk.new_scope() as scope:
            _apply(scope, where, level, context)
            sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass
