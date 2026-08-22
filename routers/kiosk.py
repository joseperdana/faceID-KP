import time
import math
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

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api", tags=["kiosk"])

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@router.post("/recognize")
@limiter.limit("30/minute")  # Abuse protection — 30 scans/min per IP is already generous for a church kiosk
async def recognize_face(
    request: Request,
    file: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
):
    import os
    is_geofence_enabled = os.getenv("ENABLE_GEOFENCE", "false").lower() in ("true", "1", "yes")
    GEREJA_LAT = -7.979261
    GEREJA_LNG = 112.625760
    MAX_RADIUS_METER = 200

    # Geofence check is strictly enforced in production when ENABLE_GEOFENCE=true
    if is_geofence_enabled:
        if lat is None or lng is None:
            return JSONResponse(status_code=403, content={"status": "error", "message": "Koordinat GPS wajib disertakan saat absensi di gereja."})
        distance = calculate_distance(GEREJA_LAT, GEREJA_LNG, lat, lng)
        if distance > MAX_RADIUS_METER:
            return JSONResponse(status_code=403, content={"status": "error", "message": f"Akses ditolak. Anda berada {int(distance)}m dari gereja."})
    elif lat is not None and lng is not None:
        # Informational logging for dev/staging
        distance = calculate_distance(GEREJA_LAT, GEREJA_LNG, lat, lng)
        if distance > MAX_RADIUS_METER:
            print(f"[Dev Note] Scan received from outside church radius ({int(distance)}m), allowed because ENABLE_GEOFENCE=false.")


    start_time = time.time()
    content = await file.read()
    
    try:
        query_vector = await starlette.concurrency.run_in_threadpool(face_service.get_embedding, content)
        if query_vector is None:
            raise HTTPException(status_code=400, detail="Wajah tidak terdeteksi")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

    if hasattr(query_vector, 'tolist'):
        query_vector = query_vector.tolist()

    # All DB calls are wrapped in run_in_threadpool — supabase-py is a synchronous library.
    # Calling it directly in an async route blocks the entire event loop.
    # run_in_threadpool offloads each call to a thread, keeping the event loop free.
    matches = await starlette.concurrency.run_in_threadpool(DBService.match_faces, query_vector)

    if not matches:
        return {"status": "unknown", "message": "Wajah tidak dikenali."}

    user = matches[0]
    user_id = user['id']
    user_name = user['full_name']

    today_start = datetime.now(timezone.utc).date().isoformat()

    # --- TOCTOU Fix: Use a targeted today-only query instead of fetching full history ---
    today_log = await starlette.concurrency.run_in_threadpool(DBService.check_user_log_today, user_id, today_start)

    # Separately fetch full history only for the stats we still need (count + last_seen)
    history = await starlette.concurrency.run_in_threadpool(DBService.get_user_history, user_id)
    total_attendance = len(history)


    last_seen = "Baru Pertama"
    for log in history:
        if log['timestamp'] < today_start:
            last_seen_date = datetime.fromisoformat(log['timestamp'][:19]).replace(tzinfo=timezone.utc)
            last_seen = (last_seen_date + timedelta(hours=7)).strftime("%d %b %Y")
            break

    if today_log:
        return {
            "status": "success",
            "message": f"Halo {user_name}, kamu sudah absen hari ini!",
            "data": {
                "name": user_name,
                "similarity_score": round(user['similarity'], 2),
                "total_attendance": total_attendance,
                "last_seen": last_seen
            }
        }

    log_data = {
        "user_id": user_id,
        "status": "Hadir",
        "method": "face",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        await starlette.concurrency.run_in_threadpool(DBService.insert_log, log_data)
        total_attendance += 1
    except Exception as e:
        # Catches DB-level UNIQUE constraint violation (Postgres code 23505 — unique_user_per_day).
        # This handles the race: if two requests passed the today_log check simultaneously,
        # the second insert will be rejected here instead of creating a duplicate entry.
        err_str = str(e)
        if "23505" in err_str or "unique" in err_str.lower():
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
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan absensi: {err_str}")

    process_time = (time.time() - start_time) * 1000
    print(f"⚡ [MLOps] Waktu Pengenalan Wajah: {process_time:.2f} ms")

    return {
        "status": "success",
        "message": f"Halo, {user_name}! Selamat datang.",
        "data": {
            "name": user_name,
            "similarity_score": round(user['similarity'], 2),
            "total_attendance": total_attendance,
            "last_seen": last_seen,
            "method": "face"
        }
    }

@router.get("/users/search")
@limiter.limit("60/minute")
async def search_users(request: Request, q: str = ""):
    """Public search endpoint for fast manual fallback autocomplete in Kiosk."""
    if not q or len(q.strip()) < 1:
        return {"status": "success", "data": []}
    try:
        results = await starlette.concurrency.run_in_threadpool(DBService.search_active_users, q.strip(), 10)
        return {"status": "success", "data": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.post("/attendance/manual-checkin")
@limiter.limit("30/minute")
async def manual_checkin(request: Request, user_id: int = Form(...)):
    """Fast manual fallback checkin when facial recognition is unavailable."""
    try:
        user_list = await starlette.concurrency.run_in_threadpool(DBService.get_user_by_id, user_id)
        if not user_list:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Jemaat tidak ditemukan."})
        
        user = user_list[0]
        user_name = user["full_name"]
        today_start = datetime.now(timezone.utc).date().isoformat()

        today_log = await starlette.concurrency.run_in_threadpool(DBService.check_user_log_today, user_id, today_start)
        history = await starlette.concurrency.run_in_threadpool(DBService.get_user_history, user_id)
        total_attendance = len(history)

        last_seen = "Baru Pertama"
        for log in history:
            if log.get("timestamp", "") < today_start:
                last_seen_date = datetime.fromisoformat(log["timestamp"][:19]).replace(tzinfo=timezone.utc)
                last_seen = (last_seen_date + timedelta(hours=7)).strftime("%d %b %Y")
                break

        if today_log:
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
            await starlette.concurrency.run_in_threadpool(DBService.insert_log, log_data)
            total_attendance += 1
        except Exception as e:
            err_str = str(e)
            if "23505" in err_str or "unique" in err_str.lower():
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
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan absensi manual: {err_str}")

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
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.post("/register")
async def register_user(
    full_name: str = Form(...), 
    gender: str = Form(...),
    phone_number: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    existing = DBService.get_user_by_name(full_name)
    if len(existing) > 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Nama sudah terdaftar!"})
    
    valid_embeddings = []
    
    for file in files:
        content = await file.read()
        embedding = await starlette.concurrency.run_in_threadpool(face_service.get_embedding, content)
        if embedding is not None:
            valid_embeddings.append(embedding)
    
    if len(valid_embeddings) == 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Wajah tidak terdeteksi jelas di semua frame. Ulangi foto."})
    
    average_embedding = np.mean(valid_embeddings, axis=0)
    embedding_list = average_embedding.tolist()
    
    # [PHASE C] Check for face duplication
    matches = DBService.match_faces(embedding_list, threshold=0.5)
    if matches:
        matched_name = matches[0]['full_name']
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Wajah ini sudah terdaftar sebagai '{matched_name}'. Gunakan tombol 'Update Wajah' jika ingin memperbarui foto."})
    
    try:
        user_data = {
            "full_name": full_name,
            "gender": gender,
            "phone_number": phone_number,
            "face_embedding": embedding_list
        }
        new_user = DBService.insert_user(user_data)
        new_user_id = new_user['id']

        log_data = {
            "user_id": new_user_id,
            "status": "Hadir (Baru)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        DBService.insert_log(log_data)

        return {
            "status": "success", 
            "message": f"Anggota baru '{full_name}' berhasil didaftarkan dengan kualitas wajah super (berdasarkan {len(valid_embeddings)} frame)!"
        }

    except Exception as e:
        print("Register Error:", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.post("/update-face")
async def update_face(
    full_name: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    existing = DBService.get_user_by_name(full_name)
    if not existing:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Nama tidak ditemukan di database!"})
        
    user_id = existing[0]['id']
    
    valid_embeddings = []
    for file in files:
        content = await file.read()
        embedding = await starlette.concurrency.run_in_threadpool(face_service.get_embedding, content)
        if embedding is not None:
            valid_embeddings.append(embedding)
            
    if len(valid_embeddings) == 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Wajah tidak terdeteksi jelas. Ulangi foto."})
        
    average_embedding = np.mean(valid_embeddings, axis=0)
    embedding_list = average_embedding.tolist()
    
    try:
        DBService.update_user(user_id, {"face_embedding": embedding_list})
        return {"status": "success", "message": f"Data wajah untuk '{full_name}' berhasil diperbarui!"}
    except Exception as e:
        print("Update Face Error:", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

