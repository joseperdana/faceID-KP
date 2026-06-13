import os
from fastapi import APIRouter, HTTPException, Response
from schemas.auth import LoginDto
from core.security import create_access_token, COOKIE_NAME

router = APIRouter(prefix="/api", tags=["auth"])
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

@router.post("/login")
def api_login(data: LoginDto, response: Response):
    if data.password == ADMIN_PASSWORD:
        token = create_access_token(data={"sub": "admin"})
        response.set_cookie(key=COOKIE_NAME, value=token, max_age=86400, httponly=True)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=401, detail="Password Salah")
