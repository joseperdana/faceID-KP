from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time
from contextlib import asynccontextmanager
import sentry_sdk
import os

load_dotenv()

from core.observability import ENVIRONMENT, RELEASE, set_request_tags, capture_event_throttled
from core.logging_setup import (
    setup_logging, log_event, resolve_request_id, sanitize_device,
    bind_request_context, reset_request_context,
)

setup_logging()
request_logger = logging.getLogger("kp.request")
ratelimit_logger = logging.getLogger("kp.ratelimit")

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



@asynccontextmanager
async def lifespan(_app):
    # Isi cache saklar fitur di latar begitu proses hidup, supaya scan pertama
    # setelah restart di tengah acara memakai nilai dari dashboard, bukan .env.
    # Tidak ditunggu: kalau Supabase lambat, kiosk tetap langsung bisa dibuka.
    from core import flags as feature_flags
    feature_flags.warm_up()
    yield


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="KPBromoMalang API", lifespan=lifespan)
app.state.limiter = limiter


def _route_template(scope) -> str:
    """Template rute (`/api/logs/{log_id}`), bukan path mentah.

    Path mentah membuat setiap ID jadi deret sendiri di Loki; template membuat
    semua request ke endpoint yang sama bisa dijumlahkan dan dihitung p95-nya.
    """
    route = scope.get("route")
    template = getattr(route, "path_format", None) or getattr(route, "path", None)
    return template or scope.get("path", "")


def _client_ip(scope) -> str:
    client = scope.get("client")
    return client[0] if client else "unknown"


async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Respons 429 tetap persis milik slowapi; yang ditambah hanya jejaknya.

    H2 dari Gibbor: semua kiosk di balik NAT Wi-Fi gereja tampak sebagai satu
    IP dan berbagi satu jatah rate limit. Tanpa baris ini, 429 tidak meninggalkan
    jejak apa pun di server dan hipotesis itu tidak bisa dibuktikan.
    """
    response = _rate_limit_exceeded_handler(request, exc)
    try:
        route = _route_template(request.scope)
        client_ip = _client_ip(request.scope)
        device = sanitize_device(request.headers.get("x-kp-device"))
        limit = str(getattr(exc, "detail", "") or "")
        log_event(
            ratelimit_logger, logging.WARNING, "rate_limited",
            route=route, client_ip=client_ip, device=device, limit=limit,
        )
        capture_event_throttled(
            f"Rate limit terlampaui di {route}",
            key=f"ratelimit:{route}",
            where="ratelimit",
            route=route,
            device=device,
            limit=limit,
        )
    except Exception:
        pass
    return response


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

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


class RequestLoggingMiddleware:
    """Satu baris `kp.request` per HTTP request, plus request_id & label perangkat.

    ASGI murni (bukan @app.middleware) dan dipasang paling luar, supaya
    duration_ms mencakup semua middleware lain dan exception yang lolos dari
    handler tetap tercatat sebagai 500 sebelum dilempar ulang ke Starlette.
    """

    _SKIP_PREFIXES = ("/static/",)
    _SKIP_PATHS = ("/favicon.ico",)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        tokens = None
        request_id = None
        try:
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
            request_id = resolve_request_id(headers.get("x-request-id"))
            device = sanitize_device(headers.get("x-kp-device"))
            tokens = bind_request_context(request_id, device)
            set_request_tags(request_id, device)
        except Exception:
            pass

        response_status = {"code": None}

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                response_status["code"] = message.get("status")
                if request_id:
                    try:
                        message = dict(message)
                        message["headers"] = list(message.get("headers", [])) + [
                            (b"x-request-id", request_id.encode("latin-1"))
                        ]
                    except Exception:
                        pass
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            self._log(scope, start, response_status["code"] or 500, failed=True)
            raise
        else:
            self._log(scope, start, response_status["code"], failed=False)
        finally:
            if tokens is not None:
                reset_request_context(tokens)

    def _log(self, scope, start, status, failed):
        try:
            path = scope.get("path", "")
            if path.startswith(self._SKIP_PREFIXES) or path in self._SKIP_PATHS:
                return
            # Uptime monitor memanggil /health tiap menit; yang menarik hanya saat gagal.
            if path == "/health" and status == 200:
                return
            level = logging.ERROR if (failed or (status or 0) >= 500) else logging.INFO
            log_event(
                request_logger, level, "request",
                exc_info=failed or None,
                method=scope.get("method"),
                path=path,
                route=_route_template(scope),
                status=status,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
                client_ip=_client_ip(scope),
            )
        except Exception:
            pass


# Dipasang setelah always_revalidate_frontend: add_middleware menaruhnya di posisi
# terluar, jadi durasinya mencakup middleware itu juga.
app.add_middleware(RequestLoggingMiddleware)


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
