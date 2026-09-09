"""Attendance records for the dashboard. Admin only (enforced at router level)."""

import logging

import starlette.concurrency
from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import check_admin_auth
from core.timezone_wib import day_bounds_utc, parse_date
from services.db_service import DBService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["attendance"], dependencies=[Depends(check_admin_auth)])


@router.get("/attendance/date/{target_date}")
async def get_attendance_by_date(target_date: str):
    try:
        day = parse_date(target_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    start_utc, end_utc = day_bounds_utc(day)
    try:
        rows = await starlette.concurrency.run_in_threadpool(
            DBService.get_logs_from_date, start_utc, end_utc
        )
    except Exception:
        logger.exception("Failed to load attendance for %s", target_date)
        raise HTTPException(status_code=503, detail="Gagal memuat data kehadiran.") from None
    return {"status": "success", "date": target_date, "data": rows}


@router.delete("/logs/{log_id}")
async def delete_log(log_id: int):
    """Remove one attendance entry.

    Needed to correct a misrecognition. Without a way to do this, a single wrong
    entry permanently distorts the retention list that Sie Pemerhati uses to
    decide who to follow up.
    """
    try:
        result = await starlette.concurrency.run_in_threadpool(DBService.delete_log, log_id)
    except Exception:
        logger.exception("Failed to delete log_id=%s", log_id)
        raise HTTPException(status_code=503, detail="Gagal menghapus entri.") from None
    if not result:
        raise HTTPException(status_code=404, detail="Entri tidak ditemukan.")
    logger.info("Attendance log %s deleted by admin", log_id)
    return {"status": "success", "message": "Entri kehadiran dihapus."}


@router.get("/all-logs")
async def get_all_logs(
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Paginated history.

    The unpaginated version silently stopped at PostgREST's 1000-row ceiling, so
    the "complete history" table quietly omitted older entries with no warning.
    """
    try:
        page = await starlette.concurrency.run_in_threadpool(
            DBService.get_all_logs_with_users, limit, offset
        )
    except Exception:
        logger.exception("Failed to load logs")
        raise HTTPException(status_code=503, detail="Gagal memuat riwayat.") from None
    return {
        "status": "success",
        "data": page["rows"],
        "total": page["total"],
        "limit": limit,
        "offset": offset,
    }
