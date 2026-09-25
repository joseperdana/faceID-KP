"""Log terstruktur (JSON per baris) + konteks per request.

Kenapa modul ini ada:
Saat Gibbor backend terasa mati dan tidak ada satu pun data untuk menjelaskan
kenapa — yang ada hanya `print()` di journald. Setiap request dan setiap
check-in sekarang meninggalkan satu baris JSON di stdout. journald menangkapnya,
lalu Grafana Loki mem-parse JSON-nya sehingga pertanyaan seperti "berapa 429
dari kiosk-03 pukul 17:04" bisa dijawab dengan query, bukan ingatan.

Aturan yang sama dengan core/observability.py: semua di sini fail-safe. Log yang
gagal ditulis tidak boleh menjatuhkan request absensi.
"""

import contextvars
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.observability import ENVIRONMENT, RELEASE

# Diisi middleware per request. contextvars ikut terbawa ke run_in_threadpool,
# jadi log yang ditulis dari thread DB pun tetap membawa request_id-nya.
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("kp_request_id", default=None)
device_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("kp_device", default=None)

_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9-]{8,64}")
_DEVICE_INVALID_RE = re.compile(r"[^a-z0-9-]+")
_DEVICE_MAX_LEN = 40

# Atribut bawaan LogRecord. Apa pun di luar daftar ini berasal dari `extra=`
# dan ikut ditulis sebagai field JSON.
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

_HANDLER_MARK = "_kp_json_handler"


def resolve_request_id(raw: Optional[str]) -> str:
    """Pakai X-Request-ID dari browser kalau bentuknya wajar, selain itu buat baru.

    Menerima ID dari klien membuat satu scan bisa dilacak dari console HP panitia
    sampai baris log server. Validasi ketat karena nilainya masuk ke log dan
    header respons — tidak boleh jadi jalan menyisipkan teks sembarang.
    """
    if raw and _REQUEST_ID_RE.fullmatch(raw):
        return raw
    return uuid.uuid4().hex[:16]


def sanitize_device(raw: Optional[str]) -> str:
    """Normalkan label perangkat (X-KP-Device) ke [a-z0-9-], maksimal 40 karakter."""
    if not raw:
        return "unknown"
    cleaned = _DEVICE_INVALID_RE.sub("-", raw.strip().lower()).strip("-")[:_DEVICE_MAX_LEN].strip("-")
    return cleaned or "unknown"


def bind_request_context(request_id: str, device: str) -> Tuple[contextvars.Token, contextvars.Token]:
    return request_id_var.set(request_id), device_var.set(device)


def reset_request_context(tokens: Tuple[contextvars.Token, contextvars.Token]) -> None:
    try:
        request_id_var.reset(tokens[0])
        device_var.reset(tokens[1])
    except Exception:
        pass


class JsonFormatter(logging.Formatter):
    """Satu objek JSON per baris dengan field bersama yang dipakai Loki untuk filter."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
            "release": RELEASE,
            "env": ENVIRONMENT,
        }
        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
            payload["device"] = device_var.get() or "unknown"

        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            if key == "kp_fields" and isinstance(value, dict):
                payload.update(value)
            else:
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class _StdoutHandler(logging.StreamHandler):
    """StreamHandler yang selalu menulis ke sys.stdout saat ini.

    StreamHandler biasa mengikat objek stdout saat dibuat. Kalau stdout diganti
    (pytest capture, reload), handler lama menulis ke file yang sudah ditutup.
    """

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _value):
        pass


def setup_logging() -> None:
    """Pasang handler JSON ke logger `kp`. Aman dipanggil berkali-kali.

    Hanya logger `kp.*` yang dikonfigurasi, bukan root: log httpx/supabase di
    level INFO memuat URL query (bisa berisi kata kunci pencarian nama), dan
    log uvicorn/gunicorn sudah punya jalurnya sendiri.
    """
    try:
        kp_logger = logging.getLogger("kp")
        if any(getattr(h, _HANDLER_MARK, False) for h in kp_logger.handlers):
            return
        handler = _StdoutHandler()
        handler.setFormatter(JsonFormatter())
        setattr(handler, _HANDLER_MARK, True)
        kp_logger.addHandler(handler)
        kp_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        # Tanpa ini baris yang sama tercetak dua kali bila suatu saat ada yang
        # memasang handler di root (mis. logging.basicConfig).
        kp_logger.propagate = False

        # Log kp.* adalah jalur ke Loki; ke Sentry sudah ada capture_error /
        # capture_event yang eksplisit. Tanpa ignore, setiap baris level error
        # menjadi issue Sentry kedua untuk kejadian yang sama.
        from sentry_sdk.integrations.logging import ignore_logger
        for name in ("kp", "kp.request", "kp.checkin", "kp.ratelimit", "kp.geofence", "kp.register", "kp.db"):
            ignore_logger(name)
    except Exception:
        pass


def log_event(logger: logging.Logger, level: int, msg: str, exc_info: Any = None, **fields: Any) -> None:
    """Tulis satu baris log terstruktur tanpa pernah melempar exception.

    Field dikirim lewat satu kunci `kp_fields` supaya nama seperti `msg` atau
    `name` tidak bentrok dengan atribut LogRecord (makeRecord melempar KeyError).
    """
    try:
        logger.log(level, msg, exc_info=exc_info, extra={"kp_fields": fields})
    except Exception:
        pass
