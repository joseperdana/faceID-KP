import time
import math
from datetime import datetime, timezone
import numpy as np
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import starlette.concurrency
from services.db_service import DBService
from face_service import face_service

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
async def recognize_face(
    file: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None)
):
    GEREJA_LAT = -7.979261
    GEREJA_LNG = 112.625760
    MAX_RADIUS_METER = 200

    if lat is not None and lng is not None:
        distance = calculate_distance(GEREJA_LAT, GEREJA_LNG, lat, lng)
        if distance > MAX_RADIUS_METER:
            return JSONResponse(status_code=403, content={"status": "error", "message": f"Akses ditolak. Anda berada {int(distance)}m dari gereja."})

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

    matches = DBService.match_faces(query_vector)
    
    if not matches:
        return {"status": "unknown", "message": "Wajah tidak dikenali."}
        
    user = matches[0]
    user_id = user['id']
    user_name = user['full_name']
    
    today_start = datetime.now(timezone.utc).date().isoformat()
    check_log = DBService.check_user_log_today(user_id, today_start)

    if len(check_log) > 0:
        return {
            "status": "success",
            "message": f"Halo {user_name}, kamu sudah absen hari ini!",
            "data": {"name": user_name, "similarity_score": round(user['similarity'], 2)}
        }

    log_data = {
        "user_id": user_id,
        "status": "Hadir",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    DBService.insert_log(log_data)
    
    process_time = (time.time() - start_time) * 1000
    print(f"⚡ [MLOps] Waktu Pengenalan Wajah: {process_time:.2f} ms")

    return {
        "status": "success",
        "message": f"Halo, {user_name}! Selamat datang.",
        "data": {"name": user_name, "similarity_score": round(user['similarity'], 2)}
    }

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
