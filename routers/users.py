"""Member management. Admin only (enforced at router level)."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from core.security import check_admin_auth
from schemas.user import UpdateUserDto
from services.db_service import DBService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users", tags=["users"], dependencies=[Depends(check_admin_auth)]
)


@router.get("")
async def get_all_users():
    try:
        users_data = DBService.get_all_users()
        for user in users_data:
            logs_count = user.pop("attendance_logs", [])
            user["attendance_count"] = logs_count[0]["count"] if logs_count else 0
        return {"status": "success", "data": users_data}
    except Exception:
        logger.exception("Failed to list users")
        raise HTTPException(status_code=503, detail="Gagal memuat data jemaat.")


@router.get("/{user_id}/history")
async def get_user_history(user_id: int):
    try:
        return {"status": "success", "data": DBService.get_user_history(user_id)}
    except Exception:
        logger.exception("Failed to load history for user_id=%s", user_id)
        raise HTTPException(status_code=503, detail="Gagal memuat riwayat kehadiran.")


@router.put("/{user_id}")
async def update_user(user_id: int, data: UpdateUserDto):
    """Partial update — only the fields actually supplied are written.

    The dashboard's edit form has no gender control, and it used to send a
    default of "Pria" whenever its client-side cache was cold. Fixing a typo in
    a woman's phone number silently changed her recorded gender, which then fed
    the commission's gender statistics.
    """
    payload = data.model_dump(exclude_unset=True, exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan yang dikirim.")
    try:
        result = DBService.update_user(user_id, payload)
    except Exception:
        logger.exception("Failed to update user_id=%s", user_id)
        raise HTTPException(status_code=503, detail="Gagal menyimpan perubahan.")
    if not result:
        # Supabase returns an empty list rather than an error for a missing row,
        # so without this check a typo'd id reported success.
        raise HTTPException(status_code=404, detail="Jemaat tidak ditemukan.")
    return {"status": "success", "data": result}


@router.delete("/{user_id}")
async def archive_user(user_id: int):
    """Archive a member. Attendance history is preserved on purpose."""
    try:
        result = DBService.soft_delete_user(user_id)
    except Exception:
        logger.exception("Failed to archive user_id=%s", user_id)
        raise HTTPException(status_code=503, detail="Gagal mengarsipkan jemaat.")
    if not result:
        raise HTTPException(status_code=404, detail="Jemaat tidak ditemukan atau sudah diarsipkan.")
    return {
        "status": "success",
        "message": "Jemaat diarsipkan. Riwayat kehadirannya tetap tersimpan untuk statistik.",
    }


@router.post("/{user_id}/restore")
async def restore_user(user_id: int):
    try:
        result = DBService.restore_user(user_id)
    except Exception:
        logger.exception("Failed to restore user_id=%s", user_id)
        raise HTTPException(status_code=503, detail="Gagal memulihkan jemaat.")
    if not result:
        raise HTTPException(status_code=404, detail="Jemaat tidak ditemukan.")
    return {"status": "success", "message": "Jemaat dipulihkan."}


@router.delete("/{user_id}/biometrics")
async def purge_biometrics(user_id: int):
    """Erase a member's face data and phone number, irreversibly.

    This is the action that actually satisfies a deletion request: archiving
    alone leaves the 512-dimension face embedding in the database forever, even
    though the old confirmation dialog told operators it had been erased.
    """
    try:
        result = DBService.purge_biometrics(user_id)
    except Exception:
        logger.exception("Failed to purge biometrics for user_id=%s", user_id)
        raise HTTPException(status_code=503, detail="Gagal menghapus data biometrik.")
    if not result:
        raise HTTPException(status_code=404, detail="Jemaat tidak ditemukan.")
    logger.warning("Biometric data purged for user_id=%s", user_id)
    return {
        "status": "success",
        "message": "Data wajah dan nomor telepon dihapus permanen. Riwayat kehadiran tetap tersimpan.",
    }
