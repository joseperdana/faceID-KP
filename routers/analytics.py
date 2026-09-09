"""Analytics and exports. Admin only (enforced at router level)."""

import logging
import time
from typing import Dict, Optional

import starlette.concurrency
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from core.security import check_admin_auth
from services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analytics"], dependencies=[Depends(check_admin_auth)])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Small TTL caches. /api/analytics scans the full log table to build the
# heatmap; without a cache, one pengurus opening the Analytics tab mid-service
# competed with face inference for the single vCPU and stalled the kiosk queue.
_STATS_TTL = 20
_ANALYTICS_TTL = 300
_cache: Dict[str, Dict] = {}


async def _cached(key: str, ttl: int, fn, *args):
    entry = _cache.get(key)
    now = time.time()
    if entry and now < entry["expires_at"]:
        return entry["data"]
    data = await starlette.concurrency.run_in_threadpool(fn, *args)
    _cache[key] = {"data": data, "expires_at": now + ttl}
    return data


@router.get("/dashboard-stats")
async def get_dashboard_stats():
    try:
        data = await _cached("stats", _STATS_TTL, AnalyticsService.calculate_dashboard_stats)
    except Exception:
        logger.exception("Dashboard stats failed")
        # 503, not a 200 carrying {"status": "error"} — an uptime check reading
        # the old response would have reported the system healthy while it was
        # completely unable to reach the database.
        raise HTTPException(status_code=503, detail="Gagal memuat statistik.")
    return {**data, "status": "success"}


@router.get("/analytics")
async def get_analytics(
    filter_type: str = Query(default="30d", pattern="^(7d|30d|90d|all)$"),
    at_risk_days: int = Query(default=21, ge=1, le=365),
):
    try:
        data = await _cached(
            f"analytics:{filter_type}:{at_risk_days}",
            _ANALYTICS_TTL,
            AnalyticsService.get_analytics_data,
            filter_type,
            at_risk_days,
        )
    except Exception:
        logger.exception("Analytics failed for filter=%s", filter_type)
        raise HTTPException(status_code=503, detail="Gagal memuat analitik.")
    return {**data, "status": "success"}


@router.get("/export-excel")
async def export_excel(
    filter_type: str = Query(default="30d", pattern="^(7d|30d|90d|all)$"),
):
    try:
        output, filename = await starlette.concurrency.run_in_threadpool(
            AnalyticsService.generate_excel_report, filter_type
        )
    except Exception:
        logger.exception("Excel export failed for filter=%s", filter_type)
        raise HTTPException(status_code=503, detail="Gagal membuat laporan.")
    return StreamingResponse(
        output,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type=XLSX_MEDIA_TYPE,
    )


@router.get("/export-excel/date/{target_date}")
async def export_excel_by_date(target_date: str):
    try:
        output, filename = await starlette.concurrency.run_in_threadpool(
            AnalyticsService.generate_daily_excel_report, target_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Daily export failed for %s", target_date)
        raise HTTPException(status_code=503, detail="Gagal membuat laporan harian.")
    return StreamingResponse(
        output,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type=XLSX_MEDIA_TYPE,
    )
