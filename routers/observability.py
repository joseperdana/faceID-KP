"""Endpoint kesehatan & penerima laporan error dari browser kiosk."""

import os
import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool

from core.observability import capture_event, ENVIRONMENT, RELEASE

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(tags=["observability"])

PROCESS_STARTED_AT = time.time()


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
