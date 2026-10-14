import logging
import os
import re
import time
from typing import Optional

import httpx
from supabase import create_client, Client, ClientOptions
from dotenv import load_dotenv

from core.logging_setup import log_event
from core.observability import capture_error

# Load environment variables
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Pastikan file .env sudah diisi dengan SUPABASE_URL dan SUPABASE_KEY")

db_logger = logging.getLogger("kp.db")

# --- Klien HTTP ke Supabase ---------------------------------------------------
# Bawaan postgrest-py adalah SATU httpx.Client dengan http2=True dan timeout
# 120 detik, dipakai bersama oleh semua thread threadpool. Saat Gibbor koneksi
# HTTP/2 itu putus di tengah antrian: sebagian panggilan gagal dengan
# RemoteProtocolError/LocalProtocolError (state h2 rusak karena dipakai
# bersamaan), sisanya menggantung sampai 120 detik — dua kali batas nginx.
#
# HTTP/1.1 memberi satu koneksi per request yang sedang jalan, jadi satu
# koneksi yang rusak hanya menggagalkan satu panggilan, bukan semuanya.
# Timeout dibuat jauh di bawah 60 detik nginx supaya server yang menjawab
# "gagal" ke kiosk, bukan nginx yang menjawab 504 setelah semua orang menunggu.
CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 10.0
WRITE_TIMEOUT_S = 10.0
POOL_TIMEOUT_S = 5.0

# Satu koneksi per thread: anyio (dipakai run_in_threadpool dan handler `def`)
# membatasi threadpool di 40 thread secara bawaan. Pool yang lebih kecil
# membuat thread saling menunggu koneksi; yang lebih besar tidak terpakai.
POOL_SIZE = int(os.getenv("SUPABASE_POOL_SIZE", "40"))

# RPC yang hanya membaca. POST ke /rpc/* diperlakukan sebagai tulis kecuali
# terdaftar di sini, karena fungsi RPC bisa saja mengubah data.
READ_ONLY_RPCS = {"match_faces"}

# Baca boleh diulang sekali untuk semua gangguan transport yang sementara:
# mengulang SELECT tidak pernah mengubah data.
READ_RETRY_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.LocalProtocolError,
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ReadTimeout,
)

# Tulis hanya diulang kalau request PASTI belum sampai ke server: koneksi tak
# pernah terbentuk, antre koneksi di pool, atau h11 menolak mengirim sebelum
# request utuh keluar (LocalProtocolError di HTTP/1.1). RemoteProtocolError dan
# ReadTimeout sengaja tidak masuk: insert-nya mungkin sudah tersimpan dan hanya
# jawabannya yang hilang. insert_user tidak punya penjaga unik, jadi mengulang
# di situ bisa menciptakan anggota kembar.
WRITE_RETRY_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.LocalProtocolError,
)

_RPC_RE = re.compile(r"/rest/v1/rpc/([^/?]+)")
_TABLE_RE = re.compile(r"/rest/v1/([^/?]+)")


def _is_read(request: httpx.Request) -> bool:
    if request.method in ("GET", "HEAD"):
        return True
    rpc = _RPC_RE.search(request.url.path)
    return bool(request.method == "POST" and rpc and rpc.group(1) in READ_ONLY_RPCS)


def _target(request: httpx.Request) -> str:
    """Nama tabel/RPC untuk log — tanpa query string (bisa berisi nama orang)."""
    m = _RPC_RE.search(request.url.path)
    if m:
        return f"rpc/{m.group(1)}"
    m = _TABLE_RE.search(request.url.path)
    return m.group(1) if m else request.url.path[:60]


class RetryingClient(httpx.Client):
    """httpx.Client yang mengulang SATU kali gangguan transport yang aman diulang.

    Ditaruh di `send`, bukan di transport, supaya kegagalan saat membaca body
    respons (bukan hanya saat menunggu header) ikut tertangkap.
    """

    def send(self, request: httpx.Request, **kwargs) -> httpx.Response:
        read = _is_read(request)
        retry_on = READ_RETRY_ERRORS if read else WRITE_RETRY_ERRORS
        try:
            return super().send(request, **kwargs)
        except retry_on as first:
            first_error = first
        log_event(
            db_logger, logging.WARNING, "db_retry",
            target=_target(request), http_method=request.method,
            kind="read" if read else "write", error_type=type(first_error).__name__,
        )
        t0 = time.perf_counter()
        try:
            return super().send(request, **kwargs)
        except httpx.TransportError as e:
            capture_error(
                e, where="db.retry_exhausted",
                target=_target(request), http_method=request.method,
                kind="read" if read else "write",
                first_error=type(first_error).__name__,
                retry_ms=round((time.perf_counter() - t0) * 1000, 1),
            )
            raise


def build_http_client(transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
    """Klien HTTP untuk Supabase. `transport` hanya diisi tes."""
    return RetryingClient(
        http2=False,
        timeout=httpx.Timeout(
            connect=CONNECT_TIMEOUT_S, read=READ_TIMEOUT_S,
            write=WRITE_TIMEOUT_S, pool=POOL_TIMEOUT_S,
        ),
        limits=httpx.Limits(
            max_connections=POOL_SIZE,
            max_keepalive_connections=POOL_SIZE,
            keepalive_expiry=30.0,
        ),
        follow_redirects=True,
        transport=transport,
    )


http_client = build_http_client()

# Inisialisasi Client. httpx_client dipakai postgrest (semua table()/rpc()),
# auth, storage, dan functions — timeout dari ClientOptions diabaikan saat
# klien sendiri diberikan, jadi batas waktunya murni dari build_http_client.
supabase: Client = create_client(url, key, options=ClientOptions(httpx_client=http_client))

print("✅ Database connection initialized.")
