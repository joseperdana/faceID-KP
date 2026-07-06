from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from services.db_service import DBService
from core.security import check_admin_auth
from schemas.user import UpdateUserDto

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(check_admin_auth)])

@router.get("")
async def get_all_users():
    try:
        users_data = DBService.get_all_users()
        logs_res = DBService.get_all_logs_raw()
        
        counts = {}
        for log in logs_res:
            uid = str(log['user_id'])
            counts[uid] = counts.get(uid, 0) + 1
            
        for u in users_data:
            u_id_str = str(u['id'])
            u['attendance_count'] = counts.get(u_id_str, 0)
            
        return users_data
    except Exception as e:
        print(f"Error Get Users: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/{user_id}/history")
async def get_user_history(user_id: str):
    try:
        res = DBService.get_user_history(user_id)
        return {"status": "success", "data": res}
    except Exception as e:
        print(f"Error User History: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.put("/{user_id}")
async def update_user(user_id: int, data: UpdateUserDto):
    try:
        res = DBService.update_user(user_id, {
            "full_name": data.full_name,
            "gender": data.gender,
            "phone_number": data.phone_number
        })
        return {"status": "success", "data": res}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.delete("/{user_id}")
async def delete_user(user_id: int):
    try:
        # Soft delete: preserves the user's attendance history in the database.
        # The user disappears from all UI queries (is_deleted=true filter).
        # Hard-deleting attendance logs alongside a user would destroy historical records.
        DBService.soft_delete_user(user_id)
        return {"status": "success", "message": "Jemaat telah diarsipkan (data kehadiran tetap tersimpan)."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
