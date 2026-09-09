"""Admin login."""

import logging

from fastapi import APIRouter, HTTPException, Request, Response

from core import config
from core.limiter import limiter
from core.security import create_access_token, set_admin_cookie, verify_admin_password
from schemas.auth import LoginDto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
@limiter.limit(config.RATE_LIMIT_LOGIN)
def api_login(request: Request, data: LoginDto, response: Response):
    if not verify_admin_password(data.password):
        raise HTTPException(status_code=401, detail="Password salah")
    token = create_access_token(data={"sub": "admin"})
    set_admin_cookie(response, token)
    return {"status": "success"}
