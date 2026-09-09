"""Kiosk endpoints: face recognition, manual fallback, and enrolment.

Authentication note. `/api/recognize` stays open: it is the kiosk's public
action, guarded by geofencing and rate limiting, and locking it risks nobody
being able to check in on a Saturday. Everything that *writes* member data or
*enumerates* members now requires an enrolled kiosk device or a signed-in
pengurus — see core.security.check_kiosk_auth. `/api/update-face` is stricter
still (admin only), because overwriting an embedding is irreversible.
"""

import logging
import math
import time

import starlette.concurrency
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from core import config
from core.limiter import limiter
from core.security import check_admin_auth, check_kiosk_auth
from core.timezone_wib import utc_now_iso
from face_service import FaceServiceUnavailable, average_embeddings, face_service
from services.attendance_service import check_in
from services.db_service import DBService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["kiosk"])

# JPEG, PNG and WebP signatures. Anything else never reaches the image decoder.
_IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")


# --- geofencing -----------------------------------------------------------


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (haversine)."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def check_geofence(
    lat: float | None,
    lng: float | None,
    accuracy: float | None = None,
) -> JSONResponse | None:
    """Reject check-ins that are demonstrably far from the venue.

    This is a convenience control, not a security control: the browser supplies
    the coordinates and the server cannot verify them. It stops accidental
    check-ins from home; it does not stop anyone who wants to spoof a location.
    Do not rely on it to prove physical presence.

    Accuracy handling matters more than it looks. Indoors the browser often
    falls back to a wifi fix accurate to kilometres. Rejecting on raw distance
    would turn away members standing at the kiosk, so a fix only fails when it
    is outside the radius *by more than its own error margin*.
    """
    if not config.ENABLE_GEOFENCE:
        return None

    if lat is None or lng is None:
        return JSONResponse(
            status_code=403,
            content={
                "status": "error",
                "message": "Izinkan akses lokasi untuk absen di gereja, atau gunakan Cari Nama Manual.",
            },
        )

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Koordinat lokasi tidak valid."},
        )

    distance = calculate_distance(config.CHURCH_LAT, config.CHURCH_LNG, lat, lng)
    margin = max(accuracy or 0.0, 0.0)
    if distance - margin > config.GEOFENCE_RADIUS_METERS:
        return JSONResponse(
            status_code=403,
            content={
                "status": "error",
                "message": f"Absen hanya bisa dilakukan di lokasi gereja. Anda terdeteksi {int(distance)} m dari lokasi.",
            },
        )
    return None


# --- upload validation ----------------------------------------------------


async def read_image_upload(file: UploadFile) -> bytes:
    """Read one uploaded image with size and type checks applied first.

    Order matters: the size limit is enforced while reading, so an oversized
    body is never fully buffered, and the magic-byte check runs before any bytes
    reach OpenCV's native decoders.
    """
    limit = config.MAX_IMAGE_BYTES
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Ukuran foto melebihi {limit // (1024 * 1024)} MB.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Foto kosong.")
    if not content.startswith(_IMAGE_MAGIC):
        raise HTTPException(status_code=415, detail="Berkas bukan gambar yang didukung.")
    return content


def validate_upload_count(files: list[UploadFile]) -> None:
    """Bound the work a single request can ask for.

    Without this, one request carrying 50 files forced 50 sequential inference
    passes on a single-vCPU box — a denial of service that costs the caller one
    curl command.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Tidak ada foto yang dikirim.")
    if len(files) > config.MAX_REGISTER_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maksimal {config.MAX_REGISTER_FILES} foto per pendaftaran.",
        )


async def embed_uploads(files: list[UploadFile]) -> list[list[float]]:
    """Extract an embedding from each uploaded frame, skipping ones without a face."""
    validate_upload_count(files)

    embeddings: list[list[float]] = []
    for file in files:
        content = await read_image_upload(file)
        try:
            embedding = await starlette.concurrency.run_in_threadpool(
                face_service.get_embedding, content
            )
        except FaceServiceUnavailable:
            raise HTTPException(
                status_code=503,
                detail="Layanan pengenalan wajah sedang tidak tersedia.",
            ) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        if embedding is not None:
            embeddings.append(embedding)
    return embeddings


# --- recognition ----------------------------------------------------------


@router.post("/recognize")
@limiter.limit(config.RATE_LIMIT_RECOGNIZE)
async def recognize_face(
    request: Request,
    file: UploadFile = File(...),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    accuracy: float | None = Form(None),
):
    geo_err = check_geofence(lat, lng, accuracy)
    if geo_err:
        return geo_err

    start_time = time.time()
    content = await read_image_upload(file)

    try:
        query_vector = await starlette.concurrency.run_in_threadpool(
            face_service.get_embedding, content
        )
    except FaceServiceUnavailable:
        # 503 rather than 500 so the kiosk can say "server bermasalah, gunakan
        # pencarian manual" instead of "wajah belum terdaftar".
        raise HTTPException(
            status_code=503,
            detail="Layanan pengenalan wajah sedang tidak tersedia. Gunakan Cari Nama Manual.",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        logger.exception("Face embedding failed")
        raise HTTPException(status_code=503, detail="Pengenalan wajah gagal diproses.") from None

    if query_vector is None:
        # Deliberately outside the try block above. When this raise lived inside
        # it, `except Exception` caught FastAPI's own HTTPException and turned a
        # routine "no face in frame" into a 500 that the kiosk rendered as
        # "wajah belum terdaftar" — sending registered members to re-register.
        raise HTTPException(status_code=400, detail="Wajah tidak terdeteksi. Coba lagi.")

    matches = await starlette.concurrency.run_in_threadpool(
        DBService.match_faces, query_vector, None, 2
    )
    if not matches:
        return {"status": "unknown", "message": "Wajah tidak dikenali."}

    best = matches[0]
    if len(matches) > 1:
        gap = best["similarity"] - matches[1]["similarity"]
        if gap < config.FACE_MATCH_MARGIN:
            # Two people are almost equally close — siblings, for instance.
            # Guessing here writes attendance under the wrong name silently.
            logger.warning(
                "Ambiguous face match: %s (%.3f) vs %s (%.3f)",
                best.get("full_name"),
                best["similarity"],
                matches[1].get("full_name"),
                matches[1]["similarity"],
            )
            return {
                "status": "ambiguous",
                "message": "Wajah mirip dengan lebih dari satu jemaat. Gunakan Cari Nama Manual.",
            }

    result = await starlette.concurrency.run_in_threadpool(
        check_in, best["id"], best["full_name"], "face", best["similarity"]
    )

    logger.info("Recognition completed in %.0f ms", (time.time() - start_time) * 1000)
    return result


# --- manual fallback ------------------------------------------------------


@router.get("/users/search", dependencies=[Depends(check_kiosk_auth)])
@limiter.limit(config.RATE_LIMIT_SEARCH)
async def search_users(request: Request, q: str = ""):
    """Name autocomplete for the kiosk's manual fallback.

    Returns id and name only. Requires an enrolled device: when this was open,
    26 requests (q=a … q=z) dumped the whole member directory including phone
    numbers.
    """
    cleaned = (q or "").strip()
    if len(cleaned) < 2:
        return {"status": "success", "data": []}
    try:
        results = await starlette.concurrency.run_in_threadpool(
            DBService.search_active_users, cleaned, 25
        )
        return {"status": "success", "data": results}
    except Exception:
        logger.exception("User search failed")
        raise HTTPException(status_code=503, detail="Pencarian sedang bermasalah.") from None


@router.post("/attendance/manual-checkin", dependencies=[Depends(check_kiosk_auth)])
@limiter.limit(config.RATE_LIMIT_CHECKIN)
async def manual_checkin(
    request: Request,
    user_id: int = Form(...),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    accuracy: float | None = Form(None),
):
    """Manual check-in when recognition is unavailable.

    Requires an enrolled kiosk. Without that, `user_id` is an arbitrary integer
    from an anonymous caller and a loop over 1..N marks the entire congregation
    present without anyone attending.
    """
    geo_err = check_geofence(lat, lng, accuracy)
    if geo_err:
        return geo_err

    user_list = await starlette.concurrency.run_in_threadpool(DBService.get_user_by_id, user_id)
    if not user_list:
        raise HTTPException(status_code=404, detail="Jemaat tidak ditemukan.")

    try:
        return await starlette.concurrency.run_in_threadpool(
            check_in, user_id, user_list[0]["full_name"], "manual"
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Manual check-in failed for user_id=%s", user_id)
        raise HTTPException(status_code=503, detail="Gagal menyimpan absensi.") from None


# --- enrolment ------------------------------------------------------------


@router.post("/register", dependencies=[Depends(check_kiosk_auth)])
@limiter.limit(config.RATE_LIMIT_REGISTER)
async def register_user(
    request: Request,
    full_name: str = Form(...),
    gender: str = Form(...),
    phone_number: str = Form(...),
    consent: bool = Form(False),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    accuracy: float | None = Form(None),
    files: list[UploadFile] = File(...),
):
    """Register a newcomer and record their attendance for today.

    Consent is mandatory and stored. Face embeddings are biometric data, which
    UU 27/2022 classifies as data pribadi spesifik requiring explicit,
    standalone consent — so this endpoint refuses to create a record without it.
    """
    if not consent:
        raise HTTPException(
            status_code=400,
            detail="Persetujuan penggunaan data wajah wajib dicentang sebelum mendaftar.",
        )

    cleaned_name = (full_name or "").strip()
    if len(cleaned_name) < 2:
        raise HTTPException(status_code=400, detail="Nama lengkap wajib diisi.")

    # Cheap validation before anything that costs a database round trip or an
    # inference pass, so a malformed request is rejected at the door.
    validate_upload_count(files)

    # Registration writes an attendance row, so it has to respect the same
    # location rule as a check-in — otherwise it is a complete geofence bypass.
    geo_err = check_geofence(lat, lng, accuracy)
    if geo_err:
        return geo_err

    existing = await starlette.concurrency.run_in_threadpool(
        DBService.get_user_by_name, cleaned_name
    )
    if existing:
        raise HTTPException(status_code=409, detail="Nama ini sudah terdaftar.")

    embeddings = await embed_uploads(files)
    if not embeddings:
        raise HTTPException(
            status_code=400,
            detail="Wajah tidak terlihat jelas di semua foto. Ulangi dengan pencahayaan lebih baik.",
        )

    try:
        embedding_list = average_embeddings(embeddings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    # The duplicate bar is deliberately looser than the recognition bar. If it
    # were stricter, a face similar enough to be matched at check-in could still
    # pass registration, and every future scan would log the wrong person.
    duplicates = await starlette.concurrency.run_in_threadpool(
        DBService.match_faces, embedding_list, config.FACE_DUPLICATE_THRESHOLD, 1
    )
    if duplicates:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Wajah ini sudah terdaftar atas nama '{duplicates[0]['full_name']}'. "
                "Hubungi pengurus bila ini keliru."
            ),
        )

    try:
        new_user = await starlette.concurrency.run_in_threadpool(
            DBService.insert_user,
            {
                "full_name": cleaned_name,
                "gender": gender,
                "phone_number": (phone_number or "").strip() or None,
                "face_embedding": embedding_list,
                "consent_at": utc_now_iso(),
                "consent_version": "1.0",
            },
        )
        await starlette.concurrency.run_in_threadpool(
            DBService.insert_log,
            {
                "user_id": new_user["id"],
                "status": "Hadir",
                "method": "register",
                "timestamp": utc_now_iso(),
            },
        )
    except Exception:
        logger.exception("Registration failed for %s", cleaned_name)
        raise HTTPException(status_code=503, detail="Gagal menyimpan pendaftaran.") from None

    return {
        "status": "success",
        "message": f"Selamat datang, {cleaned_name}! Wajahmu tersimpan dan kehadiranmu hari ini sudah dicatat.",
        "data": {"name": cleaned_name, "frames_used": len(embeddings)},
    }


@router.post("/update-face", dependencies=[Depends(check_admin_auth)])
@limiter.limit(config.RATE_LIMIT_REGISTER)
async def update_face(
    request: Request,
    full_name: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """Replace a member's stored face data. Admin only.

    Overwriting an embedding is irreversible and locks the real person out of
    the system, so this is the one enrolment action a kiosk device may not
    perform on its own.
    """
    validate_upload_count(files)

    existing = await starlette.concurrency.run_in_threadpool(DBService.get_user_by_name, full_name)
    if not existing:
        raise HTTPException(status_code=404, detail="Nama tidak ditemukan.")

    embeddings = await embed_uploads(files)
    if not embeddings:
        raise HTTPException(status_code=400, detail="Wajah tidak terdeteksi jelas. Ulangi foto.")

    try:
        embedding_list = average_embeddings(embeddings)
        await starlette.concurrency.run_in_threadpool(
            DBService.update_user, existing[0]["id"], {"face_embedding": embedding_list}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        logger.exception("Face update failed for %s", full_name)
        raise HTTPException(status_code=503, detail="Gagal memperbarui data wajah.") from None

    return {
        "status": "success",
        "message": f"Data wajah '{existing[0]['full_name']}' berhasil diperbarui.",
    }
