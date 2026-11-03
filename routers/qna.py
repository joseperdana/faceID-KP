from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from core import flags, qna_bus
from core.observability import capture_error
from services import qna_service
from services.qna_service import QnaError

router = APIRouter(tags=["qna"])
limiter = Limiter(key_func=get_remote_address)

# Sengaja `def` untuk semua handler yang memanggil qna_service: supabase-py
# sinkron, dan sebagai `async def` ia membekukan event loop seluruh proses —
# termasuk kiosk absen yang hidup di malam yang sama (lihat routers/users.py).
# Satu-satunya `async def` adalah stream SSE, yang tidak pernah menyentuh DB.

# Satu WiFi gereja = satu IP (NAT, temuan Gibbor H2). Batas per IP hanya
# penahan skrip; anti-spam sesungguhnya jeda 30 detik per HP di qna_submit.
SUBMIT_LIMIT = "60/minute"
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
