import asyncio
import json
import time
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from core import flags, qna_bus
from core.observability import capture_error
from core.security import check_admin_auth
from services import qna_service, tts_service
from services.qna_service import QnaError

router = APIRouter(tags=["qna"])
limiter = Limiter(key_func=get_remote_address)

# Sengaja `def` untuk semua handler yang memanggil qna_service: supabase-py
# sinkron, dan sebagai `async def` ia membekukan event loop seluruh proses —
# termasuk kiosk absen yang hidup di malam yang sama (lihat routers/users.py).
# Satu-satunya `async def` adalah stream SSE, yang tidak pernah menyentuh DB.

# Satu WiFi gereja = satu IP (NAT, temuan Gibbor H2), jadi ratusan HP jemaat
# tampak sebagai satu klien. Anti-spam sesungguhnya adalah jeda 30 detik per HP
# di qna_submit; batas per IP ini hanya penahan skrip, maka dibuat longgar.
SUBMIT_LIMIT = "300/minute"
VOTE_LIMIT = "300/minute"


class SubmitDto(BaseModel):
    body: str = Field(..., max_length=1000)  # batas 300 ditegakkan di DB setelah trim
    device_id: UUID


class VoteDto(BaseModel):
    device_id: UUID
    on: bool


def require_qna_enabled():
    if not flags.is_enabled("qna"):
        raise HTTPException(status_code=404, detail="Sesi tanya jawab sedang tidak aktif.")


@router.get("/tanya", dependencies=[Depends(require_qna_enabled)])
def jemaat_page():
    return FileResponse("frontend/qna/tanya.html")


@router.get("/tanya/admin", dependencies=[Depends(check_admin_auth)])
def admin_page():
    return FileResponse("frontend/qna/tanya-admin.html")


@router.get("/tanya/display", dependencies=[Depends(check_admin_auth)])
def display_page():
    return FileResponse("frontend/qna/tanya-display.html")


def _error(e: QnaError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={
        "status": "error", "code": e.code, "message": e.message, "retry_after": e.retry_after,
    })


def _call(where: str, fn, *args, **kwargs):
    """Sukses -> dict {"status": "success", ...}; selain itu JSONResponse."""
    try:
        return {"status": "success", "data": fn(*args, **kwargs)}
    except QnaError as e:
        return _error(e)
    except Exception as e:
        capture_error(e, where=f"qna.{where}")
        return JSONResponse(status_code=500, content={
            "status": "error", "code": "server", "message": "Terjadi kesalahan di server.",
            "retry_after": None,
        })


def _announce(result, *kinds: str):
    if isinstance(result, dict):
        for kind in kinds:
            qna_bus.publish(kind)
    return result


@router.get("/api/qna/state", dependencies=[Depends(require_qna_enabled)])
def get_state():
    return _call("state", qna_service.get_state)


@router.post("/api/qna/questions", dependencies=[Depends(require_qna_enabled)])
@limiter.limit(SUBMIT_LIMIT)
def submit_question(request: Request, payload: SubmitDto):
    return _announce(_call("submit", qna_service.submit, payload.body, str(payload.device_id)), "questions")


@router.get("/api/qna/questions/public", dependencies=[Depends(require_qna_enabled)])
def public_questions(device_id: UUID):
    return _call("public_list", qna_service.public_list, str(device_id))


@router.post("/api/qna/questions/{question_id}/vote", dependencies=[Depends(require_qna_enabled)])
@limiter.limit(VOTE_LIMIT)
def vote_question(request: Request, question_id: UUID, payload: VoteDto):
    return _announce(
        _call("vote", qna_service.vote, str(question_id), str(payload.device_id), payload.on),
        "questions",
    )


# Publik dan tidak dikunci flag: isinya hanya pertanyaan yang memang sedang
# tampil di videotron, dan display harus tetap jalan walau flag jemaat ditutup.
@router.get("/api/qna/display")
def display_state():
    return _call("display", qna_service.display)


QUESTION_ACTIONS = {"approve", "reject", "show", "done"}
SCREEN_ACTIONS = {"hide", "replay"}


class SettingsDto(BaseModel):
    session_open: Optional[bool] = None
    points_mode: Optional[Literal["hiasan", "upvote"]] = None
    tts_engine: Optional[Literal["browser", "cloud"]] = None


class ShowDto(BaseModel):
    # Pesan pembuka & efek dipilih admin per pertanyaan; keduanya opsional
    # (kosong = teks bawaan dan bunyi "ding").
    intro: Optional[str] = Field(default=None, max_length=120)
    sfx: Optional[Literal["ding", "tada", "confetti"]] = None


@router.get("/api/qna/admin/questions", dependencies=[Depends(check_admin_auth)])
def admin_questions():
    return _call("admin_list", qna_service.admin_list)


@router.post("/api/qna/admin/questions/{question_id}/{action}", dependencies=[Depends(check_admin_auth)])
def admin_act(question_id: UUID, action: str, payload: Optional[ShowDto] = None):
    if action not in QUESTION_ACTIONS:
        return _error(QnaError("invalid_action"))
    kinds = ("questions", "display") if action in ("show", "done") else ("questions",)
    extra = payload.model_dump() if action == "show" and payload else {}
    return _announce(_call("admin_act", qna_service.admin_act, str(question_id), action, **extra), *kinds)


@router.post("/api/qna/admin/screen/{screen_action}", dependencies=[Depends(check_admin_auth)])
def admin_screen(screen_action: str):
    if screen_action not in SCREEN_ACTIONS:
        return _error(QnaError("invalid_action"))
    return _announce(_call("admin_screen", qna_service.admin_screen, screen_action), "display")


@router.patch("/api/qna/admin/settings", dependencies=[Depends(check_admin_auth)])
def admin_settings(payload: SettingsDto):
    # "display" ikut disiarkan karena tts_engine dibaca videotron.
    return _announce(
        _call("admin_settings", qna_service.admin_settings, **payload.model_dump()),
        "settings", "display",
    )


async def event_stream(is_disconnected, max_seconds: float, ping_seconds: float = 15):
    """Sinyal perubahan untuk admin & display. Tidak pernah menyentuh DB.

    Ditutup sendiri setelah max_seconds; EventSource menyambung ulang otomatis
    (retry 2 detik). Ping tiap 15 detik menjaga koneksi di bawah batas baca
    nginx (60 detik) dan membuat klien yang sudah pergi cepat ketahuan.
    """
    q = qna_bus.subscribe()
    try:
        yield "retry: 2000\nevent: hello\ndata: {}\n\n"
        deadline = time.monotonic() + max_seconds
        while (remaining := deadline - time.monotonic()) > 0:
            if await is_disconnected():
                break
            try:
                kind = await asyncio.wait_for(q.get(), timeout=min(ping_seconds, remaining))
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            yield f"event: changed\ndata: {json.dumps({'kind': kind})}\n\n"
    finally:
        qna_bus.unsubscribe(q)


@router.get("/api/qna/admin/stream", dependencies=[Depends(check_admin_auth)])
async def admin_stream(request: Request, max_seconds: int = Query(600, ge=0, le=600)):
    return StreamingResponse(
        event_stream(request.is_disconnected, max_seconds),
        media_type="text/event-stream",
        # X-Accel-Buffering: tanpa ini nginx menahan event sampai buffer penuh.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class TtsDto(BaseModel):
    text: str = Field(..., min_length=1, max_length=400)


@router.post("/api/qna/admin/tts", dependencies=[Depends(check_admin_auth)])
def admin_tts(payload: TtsDto):
    try:
        audio = tts_service.synthesize(payload.text)
    except tts_service.TtsUnavailable:
        # Display menganggap ini tanda untuk memakai suara browser.
        return JSONResponse(status_code=503, content={
            "status": "error", "code": "tts_unavailable", "message": "Suara cloud tidak tersedia.",
            "retry_after": None,
        })
    return Response(content=audio, media_type="audio/mpeg")
