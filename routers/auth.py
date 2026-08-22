import os
from fastapi import APIRouter, HTTPException, Response, Request
from schemas.auth import LoginDto
from core.security import create_access_token, COOKIE_NAME
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api", tags=["auth"])
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

@router.post("/login")
@limiter.limit("5/minute")  # Brute-force protection — 5 attempts/min per IP
def api_login(request: Request, data: LoginDto, response: Response):
    if data.password == ADMIN_PASSWORD:
        token = create_access_token(data={"sub": "admin"})
        response.set_cookie(key=COOKIE_NAME, value=token, max_age=86400, httponly=True)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=401, detail="Password Salah")
