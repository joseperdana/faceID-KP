from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from services.analytics_service import AnalyticsService
from core.security import check_admin_auth

router = APIRouter(prefix="/api", tags=["analytics"], dependencies=[Depends(check_admin_auth)])

@router.get("/dashboard-stats")
async def get_dashboard_stats():
    try:
        data = AnalyticsService.calculate_dashboard_stats()
        data["status"] = "success"
        return data
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/analytics")
async def get_analytics(filter_type: str = "30d", at_risk_days: int = 30):
    try:
        data = AnalyticsService.get_analytics_data(filter_type, at_risk_days)
        data["status"] = "success"
        return data
    except Exception as e:
        print(f"Analytics Error: {e}") 
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/export-excel")
async def export_excel(filter_type: str = "30d"):
    try:
        output, filename = AnalyticsService.generate_excel_report(filter_type)
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/export-excel/date/{target_date}")
async def export_excel_by_date(target_date: str):
    try:
        output, filename = AnalyticsService.generate_daily_excel_report(target_date)
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
