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
import threading
import time
from contextlib import contextmanager
from typing import Dict, Iterator, Tuple

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


def set_request_tags(request_id: str, device: str) -> None:
    """Tandai scope request ini supaya event Sentry bisa dicocokkan ke baris log.

    Tag dipasang di isolation scope (satu per request di integrasi ASGI Sentry),
    jadi ikut terbawa ke error maupun trace dari request yang sama.
    """
    try:
        sentry_sdk.set_tag("request_id", request_id)
        sentry_sdk.set_tag("device", device)
    except Exception:
        pass


def set_tag(key: str, value: str) -> None:
    try:
        sentry_sdk.set_tag(key, value)
    except Exception:
        pass


@contextmanager
def safe_span(op: str, name: str) -> Iterator[None]:
    """`sentry_sdk.start_span` yang tidak bisa menjatuhkan request.

    Kegagalan membuka atau menutup span ditelan; exception dari kode di dalam
    blok tetap naik apa adanya.
    """
    span = None
    try:
        span = sentry_sdk.start_span(op=op, name=name)
        span.__enter__()
    except Exception:
        span = None
    exc_info: Tuple = (None, None, None)
    try:
        yield
    except BaseException as e:
        exc_info = (type(e), e, e.__traceback__)
        raise
    finally:
        if span is not None:
            try:
                span.__exit__(*exc_info)
            except Exception:
                pass


# key -> (waktu kirim terakhir, jumlah yang ditahan sejak itu). Per proses: dengan
# 2 worker gunicorn, batas efektifnya dua event per jendela.
_throttle_lock = threading.Lock()
_throttle_state: Dict[str, Tuple[float, int]] = {}


def capture_event_throttled(
    message: str, *, key: str, interval_s: float = 60.0, where: str, level: str = "warning", **context
) -> bool:
    """`capture_event` yang dibatasi maksimal sekali per `key` per `interval_s`.

    Untuk kejadian yang datang bergelombang (429 saat 16 kiosk berebut jatah
    rate limit): satu event sudah cukup menandai insiden, ratusan event hanya
    menghabiskan kuota Sentry. Jumlah yang ditahan ikut dikirim di event
    berikutnya supaya besarnya gelombang tetap terbaca. Log tetap mencatat semua.
    """
    try:
        now = time.monotonic()
        with _throttle_lock:
            last_sent, suppressed = _throttle_state.get(key, (None, 0))
            if last_sent is not None and now - last_sent < interval_s:
                _throttle_state[key] = (last_sent, suppressed + 1)
                return False
            _throttle_state[key] = (now, 0)
        capture_event(message, where=where, level=level, suppressed_since_last=suppressed, **context)
        return True
    except Exception:
        return False
