"""Application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core import config
from core.limiter import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

config.validate()

if config.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        # 100% traces plus 100% profiling on a single-vCPU box spent real CPU
        # competing with face inference, and exhausted the free event quota in
        # a couple of events. send_default_pii stays off: these endpoints carry
        # names, phone numbers and face images.
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=config.SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=False,
        environment=config.ENVIRONMENT,
    )

from routers import analytics, attendance, auth, kiosk, pages, photobooth, users  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FaceID-KP\n%s", config.startup_summary())
    if not config.ADMIN_PASSWORD_HASH:
        logger.warning(
            "ADMIN_PASSWORD is stored in plaintext. Generate a hash with "
            "`python scripts/hash_password.py` and set ADMIN_PASSWORD_HASH instead."
        )
    if config.COOKIE_SECURE is False and config.IS_PRODUCTION:
        logger.warning(
            "COOKIE_SECURE=false in production — session cookies will cross the network in clear."
        )

    # Load the model here rather than at import time. A failure is logged and
    # the app still serves: the kiosk falls back to manual search instead of the
    # whole service being down.
    from face_service import face_service

    if face_service.warm_up():
        logger.info("Face recognition ready.")
    else:
        logger.error("Face recognition unavailable — kiosk will run in manual-only mode.")

    yield
    logger.info("Shutting down.")


app = FastAPI(title="KPBromoMalang API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline security headers.

    The kiosk needs camera and geolocation; nothing else does. frame-ancestors
    plus X-Frame-Options stop the kiosk being framed on another origin to phish
    camera access.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(self), geolocation=(self), microphone=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        # 'unsafe-inline'/'unsafe-eval' are still required by the Tailwind play
        # CDN and the inline page scripts. Running scripts/vendor_assets.sh and
        # switching to the built stylesheet lets both be dropped.
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    if config.COOKIE_SECURE:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(401)
async def unauthorized_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": exc.detail or "Unauthorized"},
        )
    return RedirectResponse(url="/login", status_code=303)


@app.get("/healthz", include_in_schema=False)
async def healthz():
    """Readiness probe used by the deploy script's health gate."""
    from face_service import face_service

    return {
        "status": "ok",
        "face_recognition": "ready" if face_service.is_available else "unavailable",
    }


# Mount only asset directories. Mounting the whole `frontend/` directory served
# /static/dashboard.html without authentication and exposed every uploaded
# photobooth image to directory enumeration.
app.mount("/static/js", StaticFiles(directory="frontend/js"), name="static-js")
app.mount("/static/assets", StaticFiles(directory="frontend/assets"), name="static-assets")
app.mount("/static/vendor", StaticFiles(directory="frontend/vendor"), name="static-vendor")
app.mount(
    "/static/uploads/photobooth",
    StaticFiles(directory="frontend/uploads/photobooth"),
    name="static-uploads",
)

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(kiosk.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(attendance.router)
app.include_router(photobooth.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
