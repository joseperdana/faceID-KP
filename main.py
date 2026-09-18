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

from core.observability import ENVIRONMENT, RELEASE

# Sample rate diturunkan dari 1.0: dengan 70-130 check-in menumpuk di jendela
# 16:30-17:15, perekaman 100% transaksi menghabiskan kuota Sentry dalam hitungan
# minggu. Error tetap dikirim 100% — yang di-sample hanya data performa.
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),  # Move DSN out of source code — set in .env
    environment=ENVIRONMENT,
    release=RELEASE,
    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
    profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
    send_default_pii=False,
)

from routers import pages, auth, kiosk, users, analytics, attendance, photobooth, observability, flags

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="KPBromoMalang API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(401)
async def unauthorized_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
    return RedirectResponse(url="/login", status_code=303)

# Kode kiosk harus selalu segar. Tanpa ini, peramban memakai cache heuristik dari
# last-modified dan bisa menjalankan JS lama berhari-hari — di 16 perangkat yang
# pernah membuka situs sebelum deploy, itu berarti sebagian kiosk memakai versi
# lama tanpa ada yang menyadarinya. "no-cache" tetap mengizinkan cache, hanya
# mewajibkan validasi ulang: dengan ETag, biasanya cuma 304 yang ringan.
@app.middleware("http")
async def always_revalidate_frontend(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") or response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


app.mount("/static", StaticFiles(directory="frontend"), name="static")
app.mount("/docs/diagrams", StaticFiles(directory="docs/diagrams"), name="diagrams")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(kiosk.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(attendance.router)
app.include_router(photobooth.router)
app.include_router(observability.router)
app.include_router(flags.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
