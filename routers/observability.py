"""Endpoint kesehatan, penerima laporan error, dan data performa dari browser."""

import logging
import math
import os
import re
import sys
import time
from functools import partial
from typing import Annotated, Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool

from core.observability import capture_event, ENVIRONMENT, RELEASE

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(tags=["observability"])

PROCESS_STARTED_AT = time.time()

rum_logger = logging.getLogger("kp.rum")


def _check_database() -> str:
    """Query paling murah yang membuktikan Supabase benar-benar menjawab."""
    from database import supabase
    supabase.table("users").select("id").limit(1).execute()
    return "ok"


def _check_face_model() -> str:
    """Pastikan InsightFace benar-benar termuat di memori, bukan sekadar terimpor.

    Ini pembeda penting: proses bisa hidup dan melayani halaman statis dengan
    sempurna sementara model gagal dimuat — artinya absensi wajah lumpuh total
    tapi monitor eksternal tetap hijau kalau cuma mengecek `GET /`.
    """
    from face_service import face_service
    return "loaded" if getattr(face_service, "app", None) is not None else "unavailable"


def _read_proc(path: str) -> Optional[str]:
    """Baca file /proc; None bila tidak ada (macOS/Windows saat dev).

    Dipisah jadi fungsi sendiri supaya tes bisa menyuapi isi /proc palsu.
    """
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return None


def _proc_kb(text: Optional[str], key: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(rf"^{re.escape(key)}:\s+(\d+)\s*kB", text, re.MULTILINE)
    return int(m.group(1)) if m else None


def _mb(kb: Optional[int]) -> Optional[float]:
    return None if kb is None else round(kb / 1024, 1)


def _memory_snapshot() -> Dict[str, Any]:
    """RAM proses & host, tanpa psutil.

    Hipotesis H1 di MASTERPLAN: VPS kehabisan RAM saat InsightFace dimuat dan
    antrian check-in menumpuk, lalu swap membuat semuanya lambat. Angka ini
    hanya informasi — tidak pernah mengubah status /health.
    """
    mem: Dict[str, Any] = {"pid": os.getpid()}

    rss_kb = _proc_kb(_read_proc("/proc/self/status"), "VmRSS")
    if rss_kb is not None:
        mem["process_rss_mb"] = _mb(rss_kb)
    else:
        try:
            import resource  # tidak ada di Windows
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # ru_maxrss: byte di macOS, kB di Linux.
            divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
            mem["process_rss_mb"] = round(peak / divisor, 1)
            mem["rss_is_peak"] = True
        except Exception:
            pass

    meminfo = _read_proc("/proc/meminfo")
    if meminfo:
        total = _proc_kb(meminfo, "MemTotal")
        available = _proc_kb(meminfo, "MemAvailable")
        swap_total = _proc_kb(meminfo, "SwapTotal")
        swap_free = _proc_kb(meminfo, "SwapFree")
        mem["system_total_mb"] = _mb(total)
        mem["system_available_mb"] = _mb(available)
        mem["swap_total_mb"] = _mb(swap_total)
        mem["swap_used_mb"] = (
            _mb(swap_total - swap_free) if swap_total is not None and swap_free is not None else None
        )
    return mem


@router.get("/health")
async def health(request: Request):
    checks: Dict[str, str] = {}
    healthy = True

    for name, probe in (("database", _check_database), ("face_model", _check_face_model)):
        try:
            result = await run_in_threadpool(probe)
            checks[name] = result
            if result not in ("ok", "loaded"):
                healthy = False
        except Exception as e:
            checks[name] = f"error: {type(e).__name__}"
            healthy = False

    body: Dict[str, Any] = {
        "status": "ok" if healthy else "degraded",
        "environment": ENVIRONMENT,
        "release": RELEASE,
        "uptime_s": round(time.time() - PROCESS_STARTED_AT, 1),
        "checks": checks,
    }
    try:
        body["memory"] = _memory_snapshot()
    except Exception as e:
        body["memory"] = {"error": type(e).__name__}
    # 503 saat degraded supaya uptime monitor eksternal ikut menyalakan alarm,
    # bukan cuma saat proses benar-benar mati.
    return JSONResponse(status_code=200 if healthy else 503, content=body)


class ClientErrorDto(BaseModel):
    """Payload dari browser kiosk. Semua field dibatasi panjangnya karena
    endpoint ini publik — kiosk tidak login."""
    kind: str = Field(default="js_error", max_length=40)
    message: str = Field(..., max_length=500)
    source: str = Field(default="", max_length=300)
    stack: str = Field(default="", max_length=2000)
    page: str = Field(default="", max_length=300)
    user_agent: str = Field(default="", max_length=300)
    context: Optional[Dict[str, Any]] = None


@router.post("/api/client-error")
@limiter.limit("20/minute")
async def report_client_error(request: Request, payload: ClientErrorDto):
    """Terima error sisi browser (kamera ditolak, GPS timeout, JS exception).

    Tanpa ini, seluruh kelas kegagalan tersebut hanya diketahui operator yang
    berdiri di depan kiosk dan tidak pernah meninggalkan jejak di mana pun.
    """
    context = payload.context if isinstance(payload.context, dict) else {}
    capture_event(
        f"[client] {payload.message}",
        where=f"client.{payload.kind}",
        level="error",
        page=payload.page,
        source=payload.source,
        stack=payload.stack,
        user_agent=payload.user_agent,
        client_ip=get_remote_address(request),
        **{k: v for k, v in list(context.items())[:10]},
    )
    return {"status": "received"}


# ----------------------------------------------------------------------------
# RUM — data performa dari perangkat pengguna
# ----------------------------------------------------------------------------

_DEVICE_STRIP = re.compile(r"[^a-z0-9-]")


def sanitize_device(raw: Any) -> Optional[str]:
    """Label perangkat: huruf kecil, angka, tanda minus; maksimal 40 karakter."""
    if raw is None:
        return None
    # Sama persis dengan sanitizeLabel() di observability.js: `Kiosk_03` → `kiosk-03`.
    label = _DEVICE_STRIP.sub("", re.sub(r"[\s_]+", "-", str(raw).strip().lower()))[:40]
    return label or None


def _clamp(value: Any, *, hi: float, integer: bool = False) -> Optional[float]:
    """Angka dari browser dipotong ke rentang wajar, bukan ditolak.

    Satu browser yang melapor LCP 1e12 karena bug jam tidak boleh membuang
    seluruh snapshot — metrik lain di payload yang sama tetap berguna. Nilai
    yang bukan angka, NaN, atau negatif menjadi kosong.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or number < 0:
        return None
    number = min(number, hi)
    return int(round(number)) if integer else number


def _truncate(value: Any, *, max_len: int) -> Optional[str]:
    if value is None:
        return None
    return str(value)[:max_len]


def _num(hi: float):
    return Annotated[Optional[float], BeforeValidator(partial(_clamp, hi=hi))]


def _int(hi: float):
    return Annotated[Optional[int], BeforeValidator(partial(_clamp, hi=hi, integer=True))]


def _str(max_len: int):
    return Annotated[Optional[str], BeforeValidator(partial(_truncate, max_len=max_len))]


def _first_six(value: Any) -> Any:
    return value[:6] if isinstance(value, list) else None


TEN_MINUTES_MS = 600_000
THIRTY_DAYS_MS = 30 * 24 * 3600 * 1000


class RumResource(BaseModel):
    model_config = ConfigDict(extra="ignore")
    host: _str(120) = None
    path: _str(80) = None
    initiator: _str(20) = None
    duration_ms: _num(TEN_MINUTES_MS) = None
    transfer_kb: _num(1_000_000) = None


class RumDto(BaseModel):
    """Snapshot performa dari frontend/js/observability.js.

    Semua field opsional karena Safari tidak punya separuh API-nya (LCP, INP,
    longtask, deviceMemory). Field tak dikenal diabaikan supaya JS versi baru
    di HP yang belum di-refresh tidak ditolak oleh server versi lama, atau
    sebaliknya.
    """
    model_config = ConfigDict(extra="ignore")

    phase: Optional[Literal["load", "final", "periodic"]] = None
    page: _str(300) = None
    device: _str(200) = None  # disanitasi di handler
    release: _str(64) = None
    seq: _int(100) = None
    visible_ms: _int(THIRTY_DAYS_MS) = None
    interval_ms: _int(THIRTY_DAYS_MS) = None

    ttfb_ms: _int(TEN_MINUTES_MS) = None
    dom_content_loaded_ms: _int(TEN_MINUTES_MS) = None
    load_ms: _int(TEN_MINUTES_MS) = None
    transfer_kb: _num(1_000_000) = None
    fcp_ms: _int(TEN_MINUTES_MS) = None
    lcp_ms: _int(TEN_MINUTES_MS) = None
    cls: _num(100) = None
    inp_ms: _int(TEN_MINUTES_MS) = None

    longtask_count: _int(1_000_000) = None
    longtask_total_ms: _int(THIRTY_DAYS_MS) = None
    longtask_max_ms: _int(TEN_MINUTES_MS) = None

    resource_count: _int(100_000) = None
    resource_transfer_kb: _num(10_000_000) = None
    resources: Annotated[Optional[List[RumResource]], BeforeValidator(_first_six)] = None

    device_memory_gb: _num(1024) = None
    cpu_cores: _int(1024) = None
    effective_type: _str(20) = None
    downlink_mbps: _num(100_000) = None
    rtt_ms: _int(TEN_MINUTES_MS) = None
    save_data: Optional[bool] = None
    viewport: _str(20) = None
    dpr: _num(10) = None
    user_agent: _str(300) = None
    js_heap_used_mb: _num(100_000) = None
    js_heap_limit_mb: _num(100_000) = None


# Kolom tabel client_perf; field lain dari DTO masuk ke kolom jsonb `extra`.
_RUM_COLUMNS = {
    "device", "page", "phase", "release", "visible_ms",
    "ttfb_ms", "dom_content_loaded_ms", "load_ms", "transfer_kb",
    "fcp_ms", "lcp_ms", "cls", "inp_ms",
    "longtask_count", "longtask_total_ms", "longtask_max_ms",
    "resource_count", "resource_transfer_kb", "resources",
    "device_memory_gb", "cpu_cores", "effective_type", "downlink_mbps", "rtt_ms",
    "save_data", "viewport", "dpr", "user_agent", "js_heap_used_mb", "js_heap_limit_mb",
}

SLOW_LCP_MS = 6000
SLOW_LONGTASK_TOTAL_MS = 5000
SLOW_ALERT_INTERVAL_S = 3600

_insert_warned = False
_slow_alerted_at: Dict[str, float] = {}


def _insert_client_perf(row: Dict[str, Any]) -> None:
    from database import supabase
    supabase.table("client_perf").insert(row).execute()


def _rum_row(payload: RumDto, device: Optional[str]) -> Dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    data["device"] = device
    # Rilis sisi klien jarang tersedia; rilis server yang menerima hampir selalu
    # sama karena aset disajikan no-cache oleh proses yang sama.
    data.setdefault("release", RELEASE)
    row = {k: v for k, v in data.items() if k in _RUM_COLUMNS}
    extra = {k: v for k, v in data.items() if k not in _RUM_COLUMNS}
    if extra:
        row["extra"] = extra
    return row


def _should_alert_slow(payload: RumDto, device: Optional[str]) -> bool:
    if payload.phase != "load":
        return False
    slow = (payload.lcp_ms or 0) > SLOW_LCP_MS or (payload.longtask_total_ms or 0) > SLOW_LONGTASK_TOTAL_MS
    if not slow:
        return False
    key = device or "unknown"
    now = time.time()
    last = _slow_alerted_at.get(key)
    if last is not None and now - last < SLOW_ALERT_INTERVAL_S:
        return False
    if len(_slow_alerted_at) > 500:  # label anon bisa terus bertambah; jangan bocor memori
        _slow_alerted_at.clear()
    _slow_alerted_at[key] = now
    return True


@router.post("/api/rum", status_code=202)
@limiter.limit("60/minute")  # Satu HP maksimal 10 kirim per halaman; 16 kiosk di balik NAT venue masih jauh di bawah ini.
async def report_rum(request: Request, payload: RumDto):
    """Terima snapshot performa perangkat (Web Vitals, long task, RAM, jaringan).

    Tempat simpan yang awet adalah tabel `client_perf`, bukan Sentry: satu
    malam Gibbor bisa menghasilkan ratusan snapshot, dan kuota Sentry lebih
    berharga untuk error. Hanya halaman yang benar-benar lambat saat dimuat
    yang dinaikkan ke Sentry, maksimal sekali per perangkat per jam.
    """
    global _insert_warned
    device = sanitize_device(payload.device) or sanitize_device(request.headers.get("X-KP-Device"))
    row = _rum_row(payload, device)

    try:
        rum_logger.info("rum", extra={"rum": row})
    except Exception:
        pass

    try:
        await run_in_threadpool(_insert_client_perf, row)
    except Exception as e:
        # Tabel belum dimigrasi atau Supabase ngadat: data performa boleh hilang,
        # jawaban ke browser tetap 202 supaya tidak ada retry atau laporan error baru.
        if not _insert_warned:
            _insert_warned = True
            rum_logger.warning("client_perf insert gagal (%s); snapshot RUM hanya tercatat di log", type(e).__name__)

    if _should_alert_slow(payload, device):
        capture_event(
            f"[rum] halaman lambat di {device or 'unknown'}",
            where="client.rum_slow",
            level="info",
            device=device,
            page=payload.page,
            lcp_ms=payload.lcp_ms,
            longtask_total_ms=payload.longtask_total_ms,
            device_memory_gb=payload.device_memory_gb,
            cpu_cores=payload.cpu_cores,
            effective_type=payload.effective_type,
        )

    return JSONResponse(status_code=202, content={"status": "received"})
