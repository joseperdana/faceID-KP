from fastapi import APIRouter, Depends, Response, Request
from fastapi.responses import FileResponse, RedirectResponse
from core.security import check_admin_auth, check_register_access, COOKIE_NAME, REGISTER_COOKIE_NAME
from core import flags
from fastapi import HTTPException

router = APIRouter(tags=["pages"])

@router.get("/")
def kiosk_page():
    return FileResponse("frontend/index.html")

@router.get("/photobooth")
def photobooth_page():
    # Menyembunyikan tombolnya saja tidak cukup — siapa pun yang hafal alamatnya
    # tetap masuk. Saklar harus mengunci rutenya juga.
    if not flags.is_enabled("photobooth"):
        raise HTTPException(status_code=404, detail="Photobooth sedang tidak aktif.")
    return FileResponse("frontend/photobooth.html")

@router.get("/login")
def login_page():
    return FileResponse("frontend/login.html")

@router.get("/register")
def register_page(request: Request, how: str = Depends(check_register_access)):
    if not flags.is_enabled("registration"):
        raise HTTPException(status_code=404, detail="Pendaftaran sedang ditutup.")
    response = FileResponse("frontend/register.html")
    # Perangkat yang dibuka dengan ?t=... mengingat aksesnya, supaya panitia
    # tidak perlu menempel link setiap kali halaman dimuat ulang. Cookie ini
    # hanya membuka /register — dashboard tetap butuh login admin.
    if how == "token" and request.query_params.get("t"):
        response.set_cookie(
            REGISTER_COOKIE_NAME,
            request.query_params["t"],
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 2,  # cukup untuk gladi bersih + hari acara
        )
    return response

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
