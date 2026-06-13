from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone, timedelta
from services.db_service import DBService
from core.security import check_admin_auth

router = APIRouter(prefix="/api", tags=["attendance"], dependencies=[Depends(check_admin_auth)])

@router.get("/attendance/date/{target_date}")
async def get_attendance_by_date(target_date: str):
    try:
        wib_tz = timezone(timedelta(hours=7))
        start_wib = datetime.strptime(f"{target_date} 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        end_wib = datetime.strptime(f"{target_date} 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
        
        start_utc = start_wib.astimezone(timezone.utc).isoformat()
        end_utc = end_wib.astimezone(timezone.utc).isoformat()

        res = DBService.get_logs_from_date(start_utc, end_utc)
        return {"status": "success", "date": target_date, "data": res}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.delete("/logs/{log_id}")
async def delete_log(log_id: int):
    try:
        DBService.delete_log(log_id)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.get("/all-logs")
async def get_all_logs():
    try:
        res = DBService.get_all_logs_with_users()
        return {"status": "success", "data": res}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
