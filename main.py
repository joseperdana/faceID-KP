from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sentry_sdk
import os

load_dotenv()

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),  # Move DSN out of source code — set in .env
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

from routers import pages, auth, kiosk, users, analytics, attendance, photobooth

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="KPBromoMalang API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(401)
async def unauthorized_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
    return RedirectResponse(url="/login", status_code=303)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(kiosk.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(attendance.router)
app.include_router(photobooth.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
