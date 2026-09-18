from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core import flags
from core.security import check_admin_auth
from core.observability import capture_error, capture_event

router = APIRouter(prefix="/api/flags", tags=["flags"])


class ToggleDto(BaseModel):
    enabled: bool


@router.get("")
async def public_flags():
    """Dibaca kiosk untuk menyembunyikan tombol fitur yang sedang mati.

    Tanpa auth: isinya hanya keadaan tampilan, dan kiosk memang halaman publik.
    Penegakan sesungguhnya tetap di sisi server pada tiap endpoint — menyembunyikan
    tombol saja tidak menghalangi siapa pun yang hafal alamatnya.
    """
    try:
        return {"status": "success", "data": flags.all_flags()}
    except Exception as e:
        capture_error(e, where="flags.public_flags")
        # Jangan pernah menggagalkan pemuatan kiosk gara-gara saklar.
        return {"status": "success", "data": {}}


@router.get("/detail", dependencies=[Depends(check_admin_auth)])
async def flag_detail():
    return {"status": "success", "data": flags.describe()}


@router.put("/{key}", dependencies=[Depends(check_admin_auth)])
async def toggle_flag(key: str, body: ToggleDto):
    try:
        value = flags.set_flag(key, body.enabled)
        capture_event(
            "Saklar fitur diubah dari dashboard",
            where="flags.toggle_flag",
            level="info",
            flag=key,
            enabled=value,
        )
        return {"status": "success", "data": {"key": key, "enabled": value}}
    except KeyError:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Fitur '{key}' tidak dikenal."})
    except Exception as e:
        capture_error(e, where="flags.toggle_flag", flag=key)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
