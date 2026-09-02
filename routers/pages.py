from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse, RedirectResponse
from core.security import check_admin_auth, COOKIE_NAME

router = APIRouter(tags=["pages"])

@router.get("/")
def kiosk_page():
    return FileResponse("frontend/index.html")

@router.get("/photobooth")
def photobooth_page():
    return FileResponse("frontend/photobooth.html")

@router.get("/login")
def login_page():
    return FileResponse("frontend/login.html")

@router.get("/register")
def register_page(auth: bool = Depends(check_admin_auth)):
    return FileResponse("frontend/register.html")

@router.get("/dashboard")
def dashboard_page(auth: bool = Depends(check_admin_auth)):
    return FileResponse("frontend/dashboard.html")

@router.get("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return RedirectResponse(url="/login")

@router.get("/diagrams/architecture")
def diagram_architecture():
    return FileResponse("docs/diagrams/faceid-kp.architecture.html")

@router.get("/diagrams/lifecycle")
def diagram_lifecycle():
    return FileResponse("docs/diagrams/kiosk-detection.lifecycle.html")

@router.get("/diagrams/workflow")
def diagram_workflow():
    return FileResponse("docs/diagrams/photobooth-pipeline.workflow.html")
