import time
import math
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import numpy as np
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
import starlette.concurrency
from slowapi import Limiter
from slowapi.util import get_remote_address
from services.db_service import DBService
from face_service import face_service
from core.observability import capture_error, capture_event, safe_span, set_tag
from core.logging_setup import log_event
from core.normalize import normalize_name, name_key, to_e164, subscriber_digits
from core import flags

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api", tags=["kiosk"])

checkin_logger = logging.getLogger("kp.checkin")
geofence_logger = logging.getLogger("kp.geofence")
register_logger = logging.getLogger("kp.register")


class CheckinTrace:
    """Rincian waktu per tahap satu check-in, ditutup dengan satu baris `kp.checkin`.

    Menggantikan `print(... ms)` lama. H3 dari Gibbor (±5 query Supabase
    berurutan per check-in) hanya bisa dibuktikan kalau tiap tahap diukur
    terpisah — di log untuk agregasi p95, di span Sentry untuk melihat satu
    trace. Nama, nomor HP, foto, dan koordinat GPS tidak pernah ikut dicatat.
    """

    _logger = checkin_logger
    _event = "checkin"
    _outcome_tag = "checkin_outcome"

    def __init__(self, method: str):
        self.method = method
        self.started = time.perf_counter()
        self.stage_ms = {}
        self.user_id = None
        self.similarity = None
        self.fields = {}
        self.done = False

    @contextmanager
    def stage(self, name: str, op: str):
        t0 = time.perf_counter()
        try:
            with safe_span(op, name):
                yield
        except BaseException:
            self.fields["failed_stage"] = name
            raise
        finally:
            self.stage_ms[name] = round((time.perf_counter() - t0) * 1000, 1)

    def finish(self, outcome: str, **fields) -> None:
        if self.done:
            return
        self.done = True
        try:
            self.stage_ms["total"] = round((time.perf_counter() - self.started) * 1000, 1)
            payload = {"method": self.method, "outcome": outcome, "stage_ms": self.stage_ms}
            if self.user_id is not None:
                payload["user_id"] = self.user_id
            if self.similarity is not None:
                payload["similarity"] = round(float(self.similarity), 3)
            payload.update(self.fields)
            payload.update(fields)
            level = logging.ERROR if outcome == "error" else logging.INFO
            log_event(self._logger, level, self._event, **payload)
            set_tag(self._outcome_tag, outcome)
        except Exception:
            pass


class RegisterTrace(CheckinTrace):
    """Satu baris `kp.register` per pendaftaran atau update wajah.

    Saat Gibbor ada 309 respons 400 dari /api/register yang tak bisa dijelaskan:
    nama kembar, wajah tak terdeteksi, dan wajah kembar sama-sama menjawab 400
    tanpa meninggalkan jejak. `outcome` memisahkan ketiganya, `stage_ms`
    menunjukkan tahap mana yang lambat, dan `upload_kb` membuktikan apakah
    foto dari HP memang sudah mengecil.
    """

    _logger = register_logger
    _event = "register"
    _outcome_tag = "register_outcome"

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def check_geofence(lat: Optional[float], lng: Optional[float]) -> Optional[JSONResponse]:
    return _geofence_decision(lat, lng)[0]


def _geofence_decision(lat: Optional[float], lng: Optional[float]):
    """Sama dengan check_geofence, ditambah jarak (meter, int) untuk log.

    Jarak dikembalikan terpisah supaya pemanggil bisa mencatat penolakan tanpa
    pernah menulis koordinat mentah ke log.
    """
    # Saklar dashboard menang atas .env. Kalau tabelnya tak terbaca, nilainya
    # jatuh ke ENABLE_GEOFENCE — perilaku yang berlaku sebelum fitur ini ada.
    is_geofence_enabled = flags.is_enabled("geofence")
    GEREJA_LAT = -7.979261
    GEREJA_LNG = 112.625760
    MAX_RADIUS_METER = 200

    if is_geofence_enabled:
        if lat is None or lng is None:
            return JSONResponse(status_code=403, content={"status": "error", "message": "Koordinat GPS wajib diizinkan saat absensi di gereja."}), None
        distance = calculate_distance(GEREJA_LAT, GEREJA_LNG, lat, lng)
        if distance > MAX_RADIUS_METER:
            return JSONResponse(status_code=403, content={"status": "error", "message": f"Akses ditolak. Anda berada {int(distance)}m dari gereja."}), int(distance)
    elif lat is not None and lng is not None:
        distance = calculate_distance(GEREJA_LAT, GEREJA_LNG, lat, lng)
        if distance > MAX_RADIUS_METER:
            # Saat geofence dimatikan, scan dari luar radius tetap diterima. Dicatat
            # supaya kelihatan seberapa sering itu terjadi sebelum saklar dinyalakan.
            log_event(
                geofence_logger, logging.INFO, "outside_radius_allowed",
                geofence_distance_m=int(distance),
            )
    return None, None


def _geofence_rejected(trace: "CheckinTrace", response: JSONResponse, distance_m: Optional[int]) -> JSONResponse:
    trace.finish(
        "geofence_rejected",
        geofence_distance_m=distance_m,
        geofence_reason="outside_radius" if distance_m is not None else "no_gps",
    )
    return response

@router.post("/recognize")
@limiter.limit("30/minute")  # Abuse protection — 30 scans/min per IP is already generous for a church kiosk
async def recognize_face(
    request: Request,
    file: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
):
    # Isi handler dipindah ke _recognize_face apa adanya. Pembungkus ini hanya
    # menjamin setiap jalan keluar — termasuk exception yang tak tertangkap —
    # meninggalkan tepat satu baris kp.checkin.
    trace = CheckinTrace("face")
    try:
        return await _recognize_face(trace, file, lat, lng)
    except Exception as e:
        trace.finish("error", error_type=type(e).__name__, status=getattr(e, "status_code", 500))
        raise
    finally:
        trace.finish("error")


async def _recognize_face(trace: CheckinTrace, file: UploadFile, lat: Optional[float], lng: Optional[float]):
    geo_err, geo_distance = _geofence_decision(lat, lng)
    if geo_err:
        return _geofence_rejected(trace, geo_err, geo_distance)

    content = await file.read()
    
    try:
        with trace.stage("embedding", "face.embedding"):
            query_vector = await starlette.concurrency.run_in_threadpool(face_service.get_embedding, content)
        if query_vector is None:
            trace.finish("no_face")
            raise HTTPException(status_code=400, detail="Wajah tidak terdeteksi")
    except HTTPException:
        raise
    except Exception as e:
        # HTTPException tidak dilaporkan otomatis oleh integrasi Sentry, jadi
        # kegagalan model harus dilaporkan eksplisit sebelum di-raise.
        capture_error(e, where="kiosk.face_embedding")
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

    if hasattr(query_vector, 'tolist'):
        query_vector = query_vector.tolist()

    # All DB calls are wrapped in run_in_threadpool — supabase-py is a synchronous library.
    # Calling it directly in an async route blocks the entire event loop.
    # run_in_threadpool offloads each call to a thread, keeping the event loop free.
    with trace.stage("match", "face.match"):
        matches = await starlette.concurrency.run_in_threadpool(DBService.match_faces, query_vector)

    if not matches:
        trace.finish("unknown_face")
        return {"status": "unknown", "message": "Wajah tidak dikenali."}

    user = matches[0]
    user_id = user['id']
    user_name = user['full_name']
    trace.user_id = user_id
    trace.similarity = user.get('similarity')

    # Kasus D: rutin absen tapi profilnya belum pernah diisi di Lark. Sistem
    # yang mendeteksi ini, bukan pengurus yang membandingkan dua daftar manual.
    # Kegagalan di sini tidak boleh menghentikan absensi — kehadiran lebih
    # penting daripada ajakan melengkapi profil.
    try:
        with trace.stage("link_info", "db.link_info"):
            link_info = await starlette.concurrency.run_in_threadpool(DBService.get_user_link_info, user_id)
    except Exception as e:
        capture_error(e, where="kiosk.recognize_face.link_info", user_id=user_id)
        link_info = {}

    lark_prompt = {
        "needs_lark": flags.is_enabled("lark_handoff") and link_info.get("lark_status") == "pending",
        "phone_lark": subscriber_digits(link_info.get("phone_e164") or ""),
    }

    today_start = datetime.now(timezone.utc).date().isoformat()

    # --- TOCTOU Fix: Use a targeted today-only query instead of fetching full history ---
    with trace.stage("check_today", "db.check_today"):
        today_log = await starlette.concurrency.run_in_threadpool(DBService.check_user_log_today, user_id, today_start)

    # Separately fetch full history only for the stats we still need (count + last_seen)
    with trace.stage("history", "db.history"):
        history = await starlette.concurrency.run_in_threadpool(DBService.get_user_history, user_id)
    total_attendance = len(history)


    last_seen = "Baru Pertama"
    for log in history:
        ts = log.get('timestamp')
        if ts and ts < today_start:
            try:
                last_seen_date = datetime.fromisoformat(ts[:19]).replace(tzinfo=timezone.utc)
                last_seen = (last_seen_date + timedelta(hours=7)).strftime("%d %b %Y")
                break
            except Exception as e:
                capture_event(
                    "Timestamp log gagal di-parse saat menghitung last_seen",
                    where="kiosk.recognize_face.last_seen",
                    timestamp_raw=str(ts)[:40],
                    error=str(e)[:200],
                )

    if today_log:
        trace.finish("already_checked_in")
        return {
            "status": "success",
            "message": f"Halo {user_name}, kamu sudah absen hari ini!",
            "data": {
                "name": user_name,
                "similarity_score": round(user['similarity'], 2),
                "total_attendance": total_attendance,
                "last_seen": last_seen,
                **lark_prompt
            }
        }

    log_data = {
        "user_id": user_id,
        "status": "Hadir",
        "method": "face",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        with trace.stage("insert", "db.insert"):
            await starlette.concurrency.run_in_threadpool(DBService.insert_log, log_data)
        total_attendance += 1
    except Exception as e:
        # Catches DB-level UNIQUE constraint violation (Postgres code 23505 — unique_user_per_day).
        # This handles the race: if two requests passed the today_log check simultaneously,
        # the second insert will be rejected here instead of creating a duplicate entry.
        err_str = str(e)
        if "23505" in err_str or "unique" in err_str.lower():
            # Perilaku benar (TOCTOU tertangani DB), tapi tetap dicatat sebagai info:
            # frekuensinya memberi tahu seberapa sering antrian benar-benar bertabrakan.
            capture_event(
                "Race check-in duplikat tertangkap unique constraint",
                where="kiosk.recognize_face.duplicate_race",
                level="info",
                user_id=user_id,
            )
            trace.finish("duplicate_race")
            return {
                "status": "success",
                "message": f"Halo {user_name}, kamu sudah absen hari ini!",
                "data": {
                    "name": user_name,
                    "similarity_score": round(user['similarity'], 2),
                    "total_attendance": total_attendance,
                    "last_seen": last_seen,
                    "method": "face"
                }
            }
        capture_error(e, where="kiosk.recognize_face.insert_log", user_id=user_id)
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan absensi: {err_str}")

    trace.finish("success")

    return {
        "status": "success",
        "message": f"Halo, {user_name}! Selamat datang.",
        "data": {
            "name": user_name,
            "similarity_score": round(user['similarity'], 2),
            "total_attendance": total_attendance,
            "last_seen": last_seen,
            "method": "face",
            **lark_prompt
        }
    }

@router.get("/users/search")
@limiter.limit("60/minute")
async def search_users(request: Request, q: str = ""):
    """Public search endpoint for fast manual fallback autocomplete in Kiosk."""
    if not q or len(q.strip()) < 1:
        return {"status": "success", "data": []}
    try:
        results = await starlette.concurrency.run_in_threadpool(DBService.search_active_users, q.strip(), 25)
        return {"status": "success", "data": results}
    except Exception as e:
        capture_error(e, where="kiosk.search_users")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.post("/attendance/manual-checkin")
@limiter.limit("30/minute")
async def manual_checkin(
    request: Request,
    user_id: int = Form(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
):
    """Fast manual fallback checkin when facial recognition is unavailable."""
    trace = CheckinTrace("manual")
    trace.user_id = user_id
    try:
        return await _manual_checkin(trace, user_id, lat, lng)
    except Exception as e:
        trace.finish("error", error_type=type(e).__name__, status=getattr(e, "status_code", 500))
        raise
    finally:
        trace.finish("error")


async def _manual_checkin(trace: CheckinTrace, user_id: int, lat: Optional[float], lng: Optional[float]):
    geo_err, geo_distance = _geofence_decision(lat, lng)
    if geo_err:
        return _geofence_rejected(trace, geo_err, geo_distance)

    try:
        with trace.stage("get_user", "db.get_user"):
            user_list = await starlette.concurrency.run_in_threadpool(DBService.get_user_by_id, user_id)
        if not user_list:
            trace.finish("user_not_found")
            return JSONResponse(status_code=404, content={"status": "error", "message": "Jemaat tidak ditemukan."})
        
        user = user_list[0]
        user_name = user["full_name"]
        today_start = datetime.now(timezone.utc).date().isoformat()

        with trace.stage("check_today", "db.check_today"):
            today_log = await starlette.concurrency.run_in_threadpool(DBService.check_user_log_today, user_id, today_start)
        with trace.stage("history", "db.history"):
            history = await starlette.concurrency.run_in_threadpool(DBService.get_user_history, user_id)
        total_attendance = len(history)

        last_seen = "Baru Pertama"
        for log in history:
            ts = log.get("timestamp")
            if ts and ts < today_start:
                try:
                    last_seen_date = datetime.fromisoformat(ts[:19]).replace(tzinfo=timezone.utc)
                    last_seen = (last_seen_date + timedelta(hours=7)).strftime("%d %b %Y")
                    break
                except Exception as e:
                    capture_event(
                        "Timestamp log gagal di-parse saat menghitung last_seen",
                        where="kiosk.manual_checkin.last_seen",
                        timestamp_raw=str(ts)[:40],
                        error=str(e)[:200],
                    )

        if today_log:
            trace.finish("already_checked_in")
            return {
                "status": "success",
                "message": f"Halo {user_name}, kamu sudah absen hari ini!",
                "data": {
                    "name": user_name,
                    "total_attendance": total_attendance,
                    "last_seen": last_seen,
                    "method": "manual"
                }
            }

        log_data = {
            "user_id": user_id,
            "status": "Hadir",
            "method": "manual",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        try:
            with trace.stage("insert", "db.insert"):
                await starlette.concurrency.run_in_threadpool(DBService.insert_log, log_data)
            total_attendance += 1
        except Exception as e:
            err_str = str(e)
            if "23505" in err_str or "unique" in err_str.lower():
                capture_event(
                    "Race check-in duplikat tertangkap unique constraint",
                    where="kiosk.manual_checkin.duplicate_race",
                    level="info",
                    user_id=user_id,
                )
                trace.finish("duplicate_race")
                return {
                    "status": "success",
                    "message": f"Halo {user_name}, kamu sudah absen hari ini!",
                    "data": {
                        "name": user_name,
                        "total_attendance": total_attendance,
                        "last_seen": last_seen,
                        "method": "manual"
                    }
                }
            capture_error(e, where="kiosk.manual_checkin.insert_log", user_id=user_id)
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan absensi manual: {err_str}")

        trace.finish("success")
        return {
            "status": "success",
            "message": f"Absen manual berhasil! Halo, {user_name}.",
            "data": {
                "name": user_name,
                "total_attendance": total_attendance,
                "last_seen": last_seen,
                "method": "manual"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        capture_error(e, where="kiosk.manual_checkin")
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.post("/register")
async def register_user(
    full_name: str = Form(...), 
    gender: str = Form(...),
    phone_number: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    trace = RegisterTrace("register")
    try:
        return await _register_user(trace, full_name, gender, phone_number, files)
    except Exception as e:
        trace.finish("error", error_type=type(e).__name__, status=getattr(e, "status_code", 500))
        raise
    finally:
        trace.finish("error")


async def _read_embeddings(trace: CheckinTrace, files: List[UploadFile]) -> list:
    valid_embeddings = []
    upload_bytes = 0
    with trace.stage("embedding", "face.embedding"):
        for file in files:
            content = await file.read()
            upload_bytes += len(content)
            embedding = await starlette.concurrency.run_in_threadpool(face_service.get_embedding, content)
            if embedding is not None:
                valid_embeddings.append(embedding)
    trace.fields.update(
        frames=len(files),
        valid_frames=len(valid_embeddings),
        upload_kb=round(upload_bytes / 1024, 1),
    )
    return valid_embeddings


async def _register_user(trace: RegisterTrace, full_name: str, gender: str, phone_number: str, files: List[UploadFile]):
    if not flags.is_enabled("registration"):
        trace.finish("registration_closed")
        return JSONResponse(status_code=403, content={
            "status": "error",
            "message": "Pendaftaran anggota baru sedang ditutup. Hubungi pengurus."
        })

    # Normalisasi di batas sistem: format kanonik dijamin di sini, bukan
    # bergantung pada ketikan petugas counter.
    full_name = normalize_name(full_name)
    key = name_key(full_name)
    phone_e164 = to_e164(phone_number)

    # Setiap panggilan DBService lewat run_in_threadpool: supabase-py sinkron,
    # dan dipanggil langsung di sini ia membekukan seluruh proses — termasuk
    # scan di 15 kiosk lain — selama round-trip ke Supabase.
    with trace.stage("dup_name", "db.dup_name"):
        existing = await starlette.concurrency.run_in_threadpool(DBService.get_user_by_name_key, key)
    if len(existing) > 0:
        trace.finish("duplicate_name")
        # Jangan buntu. Di depan orang yang baru pertama datang, penolakan tanpa
        # jalan keluar adalah kesan pertama yang buruk — beri tahu siapa yang
        # cocok dan arahkan ke Update Wajah.
        return JSONResponse(status_code=400, content={
            "status": "error",
            "reason": "duplicate_name",
            "matched_name": existing[0]["full_name"],
            "message": f"'{existing[0]['full_name']}' sudah terdaftar. Kalau ini memang Anda, pakai tombol 'Update Wajah'. Kalau orang lain dengan nama sama, tambahkan nama belakang."
        })

    valid_embeddings = await _read_embeddings(trace, files)
    
    if len(valid_embeddings) == 0:
        trace.finish("no_face")
        return JSONResponse(status_code=400, content={"status": "error", "message": "Wajah tidak terdeteksi jelas di semua frame. Ulangi foto."})
    
    average_embedding = np.mean(valid_embeddings, axis=0)
    embedding_list = average_embedding.tolist()
    
    # [PHASE C] Check for face duplication
    with trace.stage("dup_face", "face.match"):
        matches = await starlette.concurrency.run_in_threadpool(DBService.match_faces, embedding_list, threshold=0.5)
    if matches:
        trace.similarity = matches[0].get('similarity')
        trace.finish("duplicate_face", matched_user_id=matches[0].get('id'))
        matched_name = matches[0]['full_name']
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Wajah ini sudah terdaftar sebagai '{matched_name}'. Gunakan tombol 'Update Wajah' jika ingin memperbarui foto."})
    
    try:
        # Kasus C: orangnya sudah pernah mengisi form Lark, hanya wajahnya yang
        # belum terdaftar. Sistem yang memutuskan ini lewat nomor HP — dengan 16
        # kiosk, mengandalkan petugas menanyakan hal yang sama persis di tiap
        # perangkat adalah titik gagal yang bisa dihindari.
        with trace.stage("lark_lookup", "db.lark_lookup"):
            already_in_lark = await starlette.concurrency.run_in_threadpool(
                DBService.lark_profile_exists, phone_e164
            )

        user_data = {
            "full_name": full_name,
            "gender": gender,
            "phone_number": phone_number,
            "phone_e164": phone_e164 or None,
            "name_key": key,
            "lark_status": "linked" if already_in_lark else "pending",
            "face_embedding": embedding_list
        }
        with trace.stage("insert_user", "db.insert_user"):
            new_user = await starlette.concurrency.run_in_threadpool(DBService.insert_user, user_data)
        new_user_id = new_user['id']
        trace.user_id = new_user_id

        log_data = {
            "user_id": new_user_id,
            "status": "Hadir (Baru)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with trace.stage("insert_log", "db.insert"):
            await starlette.concurrency.run_in_threadpool(DBService.insert_log, log_data)

        response = {
            "status": "success",
            "message": f"Anggota baru '{full_name}' berhasil didaftarkan dengan kualitas wajah super (berdasarkan {len(valid_embeddings)} frame)!",
            "data": {
                "full_name": full_name,
                # Bentuk yang dimengerti Lark Base: tanpa kode negara dan tanpa
                # nol depan, sama seperti 308 baris yang sudah ada di sana.
                "phone_lark": subscriber_digits(phone_number),
                # False = jangan buka form; profilnya sudah ada di Lark, atau
                # saklar Lark sedang dimatikan karena bukan acara besar.
                "needs_lark": flags.is_enabled("lark_handoff") and not already_in_lark
            }
        }
        trace.finish("success")
        return response

    except Exception as e:
        capture_error(e, where="kiosk.register_user", full_name=full_name)
        print("Register Error:", e)
        trace.finish("error", error_type=type(e).__name__, status=500)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.post("/update-face")
async def update_face(
    full_name: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    trace = RegisterTrace("update_face")
    try:
        return await _update_face(trace, full_name, files)
    except Exception as e:
        trace.finish("error", error_type=type(e).__name__, status=getattr(e, "status_code", 500))
        raise
    finally:
        trace.finish("error")


async def _update_face(trace: RegisterTrace, full_name: str, files: List[UploadFile]):
    with trace.stage("find_user", "db.find_user"):
        existing = await starlette.concurrency.run_in_threadpool(DBService.get_user_by_name, full_name)
    if not existing:
        trace.finish("not_found")
        return JSONResponse(status_code=404, content={"status": "error", "message": "Nama tidak ditemukan di database!"})
        
    user_id = existing[0]['id']
    trace.user_id = user_id
    
    valid_embeddings = await _read_embeddings(trace, files)
            
    if len(valid_embeddings) == 0:
        trace.finish("no_face")
        return JSONResponse(status_code=400, content={"status": "error", "message": "Wajah tidak terdeteksi jelas. Ulangi foto."})
        
    average_embedding = np.mean(valid_embeddings, axis=0)
    embedding_list = average_embedding.tolist()
    
    try:
        with trace.stage("update_user", "db.update_user"):
            await starlette.concurrency.run_in_threadpool(DBService.update_user, user_id, {"face_embedding": embedding_list})
        trace.finish("success")
        return {"status": "success", "message": f"Data wajah untuk '{full_name}' berhasil diperbarui!"}
    except Exception as e:
        capture_error(e, where="kiosk.update_face", full_name=full_name)
        print("Update Face Error:", e)
        trace.finish("error", error_type=type(e).__name__, status=500)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
