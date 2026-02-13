from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response, Depends, Cookie
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from database import supabase
from face_service import face_service
from datetime import datetime, date, timezone, timedelta
import shutil
import os
from uuid import uuid4
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import numpy as np
from typing import List
import sentry_sdk
import time

# Inisialisasi Sentry
sentry_sdk.init(
    dsn="https://ff28457d829bca1529a766c0a39ac98e@o4510878135484416.ingest.us.sentry.io/4510878144987136",
    traces_sample_rate=1.0, # Rekam 100% error
    profiles_sample_rate=1.0,
)

load_dotenv()

# --- CONFIG ---
app = FastAPI()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
COOKIE_NAME = os.getenv("SECRET_KEY")

# Mount folder frontend agar file css/js bisa diakses jika ada
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# --- DTOs (Data Transfer Objects) ---
class LoginDto(BaseModel):
    password: str

class UpdateUserDto(BaseModel):
    full_name: str
    phone_number: str

# --- SECURITY ---
async def check_admin_auth(request: Request):
    session_token = request.cookies.get(COOKIE_NAME)
    if session_token != "rahasia_negara":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# --- ROUTE HALAMAN (HTML) ---
@app.get("/")
def kiosk_page():
    return FileResponse("frontend/index.html")

@app.get("/login")
def login_page():
    return FileResponse("frontend/login.html")

@app.get("/register")
def register_page(auth: bool = Depends(check_admin_auth)):
    return FileResponse("frontend/register.html")

@app.get("/dashboard")
def dashboard_page(auth: bool = Depends(check_admin_auth)):
    return FileResponse("frontend/dashboard.html")

@app.get("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return RedirectResponse(url="/login")

# --- API ENDPOINTS ---

@app.post("/api/login")
def api_login(data: LoginDto, response: Response):
    if data.password == ADMIN_PASSWORD:
        response.set_cookie(key=COOKIE_NAME, value="rahasia_negara", max_age=86400)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=401, detail="Password Salah")

@app.post("/api/recognize")
async def recognize_face(file: UploadFile = File(...)):
    start_time = time.time()
    content = await file.read()
    try:
        query_vector = face_service.get_embedding(content)
        if query_vector is None:
            raise HTTPException(status_code=400, detail="Wajah tidak terdeteksi")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

    if hasattr(query_vector, 'tolist'):
        query_vector = query_vector.tolist()

    response = supabase.rpc("match_faces", {
        "query_embedding": query_vector,
        "match_threshold": 0.5,
        "match_count": 1
    }).execute()
    
    matches = response.data
    
    if not matches:
        return {"status": "unknown", "message": "Wajah tidak dikenali."}
        
    user = matches[0]
    user_id = user['id']
    user_name = user['full_name']
    
    # Cek Duplikasi Hari Ini (Pakai UTC)
    today_start = datetime.now(timezone.utc).date().isoformat()
    check_log = supabase.table("attendance_logs").select("*").eq("user_id", user_id).gte("timestamp", today_start).execute()

    if len(check_log.data) > 0:
        return {
            "status": "success",
            "message": f"Halo {user_name}, kamu sudah absen hari ini!",
            "data": {"name": user_name, "similarity_score": round(user['similarity'], 2)}
        }

    # Catat Absen
    log_data = {
        "user_id": user_id,
        "status": "Hadir",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("attendance_logs").insert(log_data).execute()
    
    process_time = (time.time() - start_time) * 1000
    print(f"⚡ [MLOps] Waktu Pengenalan Wajah: {process_time:.2f} ms") # Muncul di terminal

    return {
        "status": "success",
        "message": f"Halo, {user_name}! Selamat datang.",
        "data": {"name": user_name, "similarity_score": round(user['similarity'], 2)}
    }

@app.post("/api/register")
async def register_user(
    full_name: str = Form(...), 
    phone_number: str = Form(...), 
    files: List[UploadFile] = File(...)
    ):
    # 1. Cek User Duplikat
    existing = supabase.table("users").select("id").eq("full_name", full_name).execute()
    if len(existing.data) > 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Nama sudah terdaftar!"})
    
    # 2. Proses Multi-Frame (Burst Capture)
    valid_embeddings = []
    
    for file in files:
        content = await file.read()
        embedding = face_service.get_embedding(content)
        if embedding is not None:
            valid_embeddings.append(embedding)
    
    # Jika dari semua foto tidak ada satupun wajah yang terdeteksi
    if len(valid_embeddings) == 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Wajah tidak terdeteksi jelas di semua frame. Ulangi foto."})
    
    # 3. KUNCI RAHASIA STABILITAS: Rata-ratakan (Average) semua embedding yang valid
    # Ini akan membuang noise (micro-blur) dan membuat referensi wajah sangat solid
    average_embedding = np.mean(valid_embeddings, axis=0)
    
    # Convert balik ke list agar bisa disimpan ke Supabase
    embedding_list = average_embedding.tolist()
    
    try:
        # 4. Simpan ke Tabel USERS
        user_data = {
            "full_name": full_name,
            "phone_number": phone_number,
            "face_embedding": embedding_list
        }
        user_res = supabase.table("users").insert(user_data).execute()
        new_user_id = user_res.data[0]['id']

        # 5. AUTO ABSEN
        log_data = {
            "user_id": new_user_id,
            "status": "Hadir (Baru)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("attendance_logs").insert(log_data).execute()

        return {
            "status": "success", 
            "message": f"Anggota baru '{full_name}' berhasil didaftarkan dengan kualitas wajah super (berdasarkan {len(valid_embeddings)} frame)!"
        }

    except Exception as e:
        print("Register Error:", e)
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

# --- 📊 API BARU UNTUK DASHBOARD PRO ---

@app.get("/api/dashboard-stats")
async def get_dashboard_stats(auth: bool = Depends(check_admin_auth)):
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        
        # 1. Total User Terdaftar
        users_res = supabase.table("users").select("id", count="exact").execute()
        total_users = users_res.count

        # 2. Kehadiran Hari Ini
        logs_today = supabase.table("attendance_logs").select("*").gte("timestamp", today).execute()
        total_present_today = len(logs_today.data)

        # 3. Baru Daftar Hari Ini
        new_users_today = supabase.table("users").select("*").gte("created_at", today).execute()
        total_new_users = len(new_users_today.data)

        # 4. Live Feed (5 Terakhir)
        feed = supabase.table("attendance_logs").select("id, timestamp, status, users(full_name)").order("timestamp", desc=True).limit(5).execute()

        return {
            "status": "success",
            "total_users": total_users,
            "present_today": total_present_today,
            "new_users_today": total_new_users,
            "recent_logs": feed.data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Pastikan import Optional ada di paling atas: from typing import Optional

@app.get("/api/analytics")
async def get_analytics(filter_type: str = "30d", at_risk_days: int = 30, auth: bool = Depends(check_admin_auth)):
    try:
        now = datetime.now(timezone.utc)
        
        # 1. TENTUKAN START DATE (Sesuai filter)
        if filter_type == "7d":
            start_date = (now - timedelta(days=7))
            days_count = 7
        elif filter_type == "90d":
            start_date = (now - timedelta(days=90))
            days_count = 90
        elif filter_type == "all":
            start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
            days_count = (now - start_date).days
        else:
            start_date = (now - timedelta(days=30))
            days_count = 30
            
        start_date_iso = start_date.isoformat()
        
        # 2. QUERY DB
        logs_query = supabase.table("attendance_logs")\
            .select("timestamp, user_id, users(full_name, phone_number)")\
            .gte("timestamp", start_date_iso)\
            .order("timestamp", desc=False)\
            .execute()
        
        logs_data = logs_query.data

        # 3. OLAH GRAFIK & HEATMAP
        date_counts = {}
        loop_range = min(days_count, 365) 
        for i in range(loop_range):
            d = (now - timedelta(days=i)).date().isoformat()
            date_counts[d] = 0
            
        for log in logs_data:
            d = log['timestamp'][:10]
            if d in date_counts:
                date_counts[d] += 1
            elif filter_type == 'all':
                 pass 
        
        sorted_dates = sorted(date_counts.keys())
        trend_data = [date_counts[d] for d in sorted_dates]
        
        # 4. RATA-RATA
        active_days_values = [v for v in trend_data if v > 0]
        total_attendance = sum(active_days_values)
        active_days_count = len(active_days_values)
        avg_attendance = round(total_attendance / active_days_count, 1) if active_days_count > 0 else 0

        # 5. TOP USER & PEAK TIME
        user_attendance_count = {}
        hour_counts = {}
        for i in range(24): hour_counts[f"{i:02}:00"] = 0

        for log in logs_data:
            if log['users']:
                name = log['users']['full_name']
                user_attendance_count[name] = user_attendance_count.get(name, 0) + 1
            
            try:
                hour_utc = int(log['timestamp'][11:13]) 
                hour_wib = (hour_utc + 7) % 24
                hour_counts[f"{hour_wib:02}:00"] += 1
            except:
                pass

        # PERUBAHAN: Hapus limit [:5], ambil SEMUA data yang sudah di-sort!
        top_users = sorted(user_attendance_count.items(), key=lambda x: x[1], reverse=True)
        peak_time_data = {k: v for k, v in hour_counts.items() if v > 0}
        
        # 6. AT RISK JEMAAT (Dengan Parameter Dinamis)
        all_users = supabase.table("users").select("id, full_name, phone_number").execute()
        all_logs_raw = supabase.table("attendance_logs").select("user_id, timestamp").order("timestamp", desc=True).limit(3000).execute()
        
        last_seen_map = {}
        for log in all_logs_raw.data:
            uid = log['user_id']
            if uid not in last_seen_map:
                last_seen_map[uid] = log['timestamp']
        
        at_risk_list = []
        for user in all_users.data:
            uid = user['id']
            last_seen = last_seen_map.get(uid)
            
            is_missing = False
            days_missing = 0
            
            if not last_seen:
                is_missing = True
                days_missing = 999 
            else:
                last_date = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                delta = now - last_date
                # PERUBAHAN: Gunakan variabel dinamis `at_risk_days` dari parameter fungsi
                if delta.days > at_risk_days:
                    is_missing = True
                    days_missing = delta.days
            
            if is_missing:
                at_risk_list.append({
                    "name": user['full_name'],
                    "phone": user['phone_number'],
                    "days_absent": days_missing
                })

        # PERUBAHAN: Hapus limit [:10], ambil semua yang memenuhi syarat!
        at_risk_list = sorted(at_risk_list, key=lambda x: x['days_absent'], reverse=True)

        return {
            "status": "success",
            "filter_used": filter_type,
            "trend": { "labels": sorted_dates, "data": trend_data },
            "avg_attendance": avg_attendance,
            "top_users": [{"name": k, "count": v} for k, v in top_users],
            "peak_time": peak_time_data,
            "at_risk": at_risk_list 
        }

    except Exception as e:
        print(f"Analytics Error: {e}") 
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    
@app.get("/api/export-excel")
async def export_excel(filter_type: str = "30d", auth: bool = Depends(check_admin_auth)):
    try:
        now = datetime.now(timezone.utc)
        
        # 1. LOGIC FILTER WAKTU (Copy dari Analytics biar konsisten)
        if filter_type == "7d":
            start_date = (now - timedelta(days=7))
        elif filter_type == "90d":
            start_date = (now - timedelta(days=90))
        elif filter_type == "all":
            start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        else:
            start_date = (now - timedelta(days=30)) # Default
            
        start_date_iso = start_date.isoformat()

        # 2. AMBIL DATA DARI SUPABASE
        # Kita butuh data lengkap: Nama, HP, Waktu, Status
        logs_query = supabase.table("attendance_logs")\
            .select("timestamp, status, users(full_name, phone_number)")\
            .gte("timestamp", start_date_iso)\
            .order("timestamp", desc=True)\
            .execute()
        
        data_raw = logs_query.data

        if not data_raw:
            # Kalau kosong, buat DataFrame kosong biar gak error
            df = pd.DataFrame(columns=["Waktu", "Nama Lengkap", "No. HP", "Status"])
        else:
            # 3. RAPIKAN DATA (Flattening JSON)
            clean_data = []
            for item in data_raw:
                # Konversi Waktu UTC ke WIB (UTC+7)
                dt_utc = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                dt_wib = dt_utc + timedelta(hours=7)
                formatted_time = dt_wib.strftime('%d-%m-%Y %H:%M:%S') # Format Tanggal Indonesia
                
                user_info = item['users'] if item['users'] else {"full_name": "User Terhapus", "phone_number": "-"}

                clean_data.append({
                    "Waktu Absen (WIB)": formatted_time,
                    "Nama Lengkap": user_info['full_name'],
                    "No. HP": user_info['phone_number'],
                    "Status Kehadiran": item['status']
                })
            
            # Buat DataFrame Pandas
            df = pd.DataFrame(clean_data)

        # 4. BUAT FILE EXCEL DI MEMORI (Tanpa simpan ke harddisk)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Laporan Absensi')
        
        output.seek(0) # Reset pointer file ke awal

        # 5. BERIKAN NAMA FILE DINAMIS
        filename = f"Laporan_Absensi_{filter_type}_{now.strftime('%Y%m%d')}.xlsx"
        
        # Return sebagai File Download
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        print(f"Export Error: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# --- 🛠️ API MANAJEMEN DATA ---

# --- 1. API GET SEMUA USER (PERBAIKAN TIPE DATA) ---
@app.get("/api/users")
async def get_all_users(auth: bool = Depends(check_admin_auth)):
    try:
        users_res = supabase.table("users").select("*").execute()
        logs_res = supabase.table("attendance_logs").select("user_id").execute()
        
        counts = {}
        for log in logs_res.data:
            uid = str(log['user_id']) # Ubah ke string agar aman
            counts[uid] = counts.get(uid, 0) + 1
            
        users_data = users_res.data
        for u in users_data:
            u_id_str = str(u['id'])
            u['attendance_count'] = counts.get(u_id_str, 0)
            
        return users_data
    except Exception as e:
        print(f"Error Get Users: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# --- 2. API RIWAYAT DETAIL (KALENDER TANPA BATAS) ---
@app.get("/api/users/{user_id}/history")
async def get_user_history(user_id: str, auth: bool = Depends(check_admin_auth)): # user_id diubah ke string
    try:
        # Ambil SEMUA riwayat user ini tanpa dilimit, agar kalender bisa mundur jauh
        res = supabase.table("attendance_logs")\
            .select("timestamp, status")\
            .eq("user_id", user_id)\
            .order("timestamp", desc=True)\
            .execute()
            
        return {"status": "success", "data": res.data}
    except Exception as e:
        print(f"Error User History: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/api/attendance/date/{target_date}")
async def get_attendance_by_date(target_date: str, auth: bool = Depends(check_admin_auth)):
    try:
        wib_tz = timezone(timedelta(hours=7))
        start_wib = datetime.strptime(f"{target_date} 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        end_wib = datetime.strptime(f"{target_date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        
        start_utc = start_wib.astimezone(timezone.utc).isoformat()
        end_utc = end_wib.astimezone(timezone.utc).isoformat()

        res = supabase.table("attendance_logs")\
            .select("timestamp, status, users(full_name, phone_number)")\
            .gte("timestamp", start_utc)\
            .lte("timestamp", end_utc)\
            .order("timestamp", desc=False)\
            .execute()

        return {"status": "success", "date": target_date, "data": res.data}
    except Exception as e:
        print(f"Error Get Daily: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.put("/api/users/{user_id}")
async def update_user(user_id: int, data: UpdateUserDto, auth: bool = Depends(check_admin_auth)):
    try:
        res = supabase.table("users").update({
            "full_name": data.full_name,
            "phone_number": data.phone_number
        }).eq("id", user_id).execute()
        return {"status": "success", "data": res.data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, auth: bool = Depends(check_admin_auth)):
    try:
        # Hapus Logs dulu (Foreign Key Constraint biasanya)
        supabase.table("attendance_logs").delete().eq("user_id", user_id).execute()
        # Baru hapus User
        supabase.table("users").delete().eq("id", user_id).execute()
        return {"status": "success", "message": "User dan data absensinya dihapus."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@app.delete("/api/logs/{log_id}")
async def delete_log(log_id: int, auth: bool = Depends(check_admin_auth)):
    try:
        supabase.table("attendance_logs").delete().eq("id", log_id).execute()
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

# --- API UNTUK RIWAYAT ABSENSI LENGKAP ---

@app.get("/api/all-logs")
async def get_all_logs(auth: bool = Depends(check_admin_auth)):
    try:
        # Ambil semua data absensi, urutkan dari yang paling baru
        res = supabase.table("attendance_logs")\
            .select("id, timestamp, status, users(full_name)")\
            .order("timestamp", desc=True)\
            .execute()
            
        return {"status": "success", "data": res.data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# ==========================================
# 2. API EXPORT EXCEL KHUSUS 1 HARI SAJA
# ==========================================
@app.get("/api/export-excel/date/{target_date}")
async def export_excel_by_date(target_date: str, auth: bool = Depends(check_admin_auth)):
    try:
        wib_tz = timezone(timedelta(hours=7))
        start_wib = datetime.strptime(f"{target_date} 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        end_wib = datetime.strptime(f"{target_date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        
        start_utc = start_wib.astimezone(timezone.utc).isoformat()
        end_utc = end_wib.astimezone(timezone.utc).isoformat()

        res = supabase.table("attendance_logs")\
            .select("timestamp, status, users(full_name, phone_number)")\
            .gte("timestamp", start_utc)\
            .lte("timestamp", end_utc)\
            .order("timestamp", desc=False)\
            .execute()
        
        data_raw = res.data
        
        if not data_raw:
            df = pd.DataFrame(columns=["Waktu Datang (WIB)", "Nama Lengkap", "No. HP", "Status Kehadiran"])
        else:
            clean_data = []
            for item in data_raw:
                dt_utc = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                dt_wib = dt_utc + timedelta(hours=7)
                formatted_time = dt_wib.strftime('%H:%M:%S') # Hanya jam saja biar rapi
                
                user_info = item['users'] if item['users'] else {"full_name": "User Terhapus", "phone_number": "-"}

                clean_data.append({
                    "Waktu Datang (WIB)": formatted_time,
                    "Nama Lengkap": user_info['full_name'],
                    "No. HP": user_info['phone_number'],
                    "Status Kehadiran": item['status']
                })
            df = pd.DataFrame(clean_data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'Absen_{target_date}')
        output.seek(0)

        filename = f"Absensi_GKI_Bromo_{target_date}.xlsx"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        print(f"Export Daily Error: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    # Jalankan server di port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)