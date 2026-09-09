"""KP45 event photobooth: strip upload and public view page.

Kept deliberately narrow. This is an event feature that shares a process and a
disk with the attendance service, so its failure modes must not be able to take
attendance down: uploads are rate limited, size-checked before decoding, and
old files are pruned.
"""

import base64
import binascii
import logging
import os
import re
import socket
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import starlette.concurrency
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from core import config
from core.limiter import limiter
from core.timezone_wib import utc_now_iso

logger = logging.getLogger(__name__)

router = APIRouter(tags=["photobooth"])

UPLOAD_DIR = Path("frontend/uploads/photobooth")
TEMPLATE_DIR = Path("frontend/templates")

_PHOTO_ID = re.compile(r"^[0-9a-f]{32}$")
_JPEG_MAGIC = b"\xff\xd8\xff"
_GIF_MAGIC = (b"GIF87a", b"GIF89a")

# Base64 expands by 4/3; a small slack covers padding and the data: prefix.
_B64_OVERHEAD = 4 / 3
_PRUNE_INTERVAL = 3600
_last_prune = 0.0


class PhotoboothUploadDto(BaseModel):
    image: str = Field(..., description="Base64 JPEG of the composed strip")
    gif_image: str | None = Field(default="", description="Base64 animated GIF")
    frame: str = Field(default="3-strip", max_length=40)
    caption: str = Field(default="", max_length=120)


def _decode_media(raw: str, magic, label: str, max_bytes: int) -> bytes:
    """Decode a base64 data URL after checking its size and signature.

    The length check runs on the encoded string, before decoding: the previous
    order allocated the full payload in memory and only then complained that it
    was too large, which is exactly backwards for a denial-of-service guard.
    """
    payload = raw.split(",", 1)[1] if "," in raw else raw
    if len(payload) > int(max_bytes * _B64_OVERHEAD) + 64:
        raise HTTPException(status_code=413, detail=f"Ukuran {label} melebihi batas.")
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail=f"Data {label} tidak valid.") from None
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Ukuran {label} melebihi batas.")
    if not data.startswith(magic):
        raise HTTPException(status_code=415, detail=f"Berkas {label} bukan format yang benar.")
    return data


def prune_old_photos(retention_days: int | None = None) -> int:
    """Delete strips older than the retention window.

    Without this, one evening of ~100 sessions leaves roughly 300 MB behind
    permanently, on the same 60 GB disk that carries the swapfile the face model
    depends on.
    """
    days = retention_days if retention_days is not None else config.PHOTOBOOTH_RETENTION_DAYS
    if days <= 0:
        return 0
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    removed = 0
    for path in UPLOAD_DIR.glob("*"):
        if path.name == ".gitkeep" or not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            logger.warning("Could not remove %s", path)
    if removed:
        logger.info("Pruned %d expired photobooth files", removed)
    return removed


def _maybe_prune() -> None:
    global _last_prune
    now = time.time()
    if now - _last_prune > _PRUNE_INTERVAL:
        _last_prune = now
        try:
            prune_old_photos()
        except Exception:
            logger.exception("Photobooth prune failed")


def get_public_base_url() -> str:
    configured = os.getenv("PHOTOBOOTH_BASE_URL")
    if configured:
        return configured.rstrip("/")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.1)
        sock.connect(("8.8.8.8", 80))
        lan_ip = sock.getsockname()[0]
        sock.close()
        return f"http://{lan_ip}:8000"
    except OSError:
        return "http://localhost:8000"


def _write(path: Path, data: bytes) -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@router.post("/api/photobooth/upload")
@limiter.limit(config.RATE_LIMIT_PHOTOBOOTH)
async def upload_photobooth_strip(request: Request, payload: PhotoboothUploadDto):
    _maybe_prune()

    image_bytes = _decode_media(payload.image, _JPEG_MAGIC, "foto", config.PHOTOBOOTH_MAX_BYTES)

    # Full 128-bit id. The previous 8 hex characters were guessable, so anyone
    # could enumerate other people's photos.
    photo_id = uuid.uuid4().hex
    gif_download_url = None

    try:
        await starlette.concurrency.run_in_threadpool(
            _write, UPLOAD_DIR / f"{photo_id}.jpg", image_bytes
        )
        if payload.gif_image and len(payload.gif_image) > 50:
            gif_bytes = _decode_media(
                payload.gif_image, _GIF_MAGIC, "GIF", config.PHOTOBOOTH_MAX_BYTES
            )
            await starlette.concurrency.run_in_threadpool(
                _write, UPLOAD_DIR / f"{photo_id}.gif", gif_bytes
            )
            gif_download_url = f"/static/uploads/photobooth/{photo_id}.gif"
    except HTTPException:
        # Re-raised before the generic handler below. When a bare
        # `except Exception` sat here, a 413 "file too large" was converted into
        # a 500 and the booth reported a server crash instead of the real cause.
        raise
    except OSError:
        logger.exception("Failed to write photobooth files")
        raise HTTPException(status_code=507, detail="Penyimpanan penuh. Hubungi panitia.") from None

    base_host = get_public_base_url()
    return {
        "status": "success",
        "photo_id": photo_id,
        "view_url": f"/p/{photo_id}",
        "download_url": f"/static/uploads/photobooth/{photo_id}.jpg",
        "gif_download_url": gif_download_url,
        "qr_url": f"{base_host}/p/{photo_id}",
        "created_at": utc_now_iso(),
    }


@router.get("/p/{photo_id}", response_class=HTMLResponse)
async def view_photobooth_photo(photo_id: str):
    # Defence in depth: Starlette's path converter already refuses a slash, but
    # an explicit shape check keeps the filename construction obviously safe.
    if not _PHOTO_ID.match(photo_id):
        return HTMLResponse(_render("photo_missing.html", {}), status_code=404)

    image_path = UPLOAD_DIR / f"{photo_id}.jpg"
    if not image_path.exists():
        return HTMLResponse(_render("photo_missing.html", {}), status_code=404)

    has_gif = (UPLOAD_DIR / f"{photo_id}.gif").exists()
    return HTMLResponse(
        _render(
            "photo_view.html",
            {
                "PHOTO_ID": photo_id,
                "IMAGE_SRC": f"/static/uploads/photobooth/{photo_id}.jpg",
                "GIF_SRC": f"/static/uploads/photobooth/{photo_id}.gif" if has_gif else "",
                "TABS_DISPLAY": "flex" if has_gif else "hidden",
            },
        )
    )


def _render(template_name: str, values: dict) -> str:
    """Fill a template with placeholder substitution.

    These pages used to be 140-line f-strings inside the router, where every CSS
    brace had to be doubled. Keeping them as real HTML files means they can be
    edited like the rest of the frontend.
    """
    template = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template
