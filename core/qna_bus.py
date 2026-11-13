"""Siaran "ada perubahan" ke koneksi SSE admin dan display tanya jawab.

Yang disiarkan hanya jenis perubahannya (questions/display/settings), bukan
datanya: klien mengambil ulang lewat endpoint biasa. Dengan begitu koneksi
SSE tidak pernah menyentuh database, dan klien yang ketinggalan sinyal tetap
benar karena polling cadangan 5 detik membaca keadaan yang sama.

Hanya berlaku dalam satu proses. Produksi memakai satu proses uvicorn
(scripts/deploy_vps.sh); kalau suatu saat multi-worker, polling cadangan
tetap menjaga semuanya berjalan, hanya sedikit lebih lambat.
"""
import asyncio
import threading
from typing import Set, Tuple

MAX_QUEUE = 16

_subscribers: Set[Tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
_lock = threading.Lock()


def subscribe() -> asyncio.Queue:
    """Dipanggil dari dalam event loop (generator SSE)."""
    q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE)
    with _lock:
        _subscribers.add((asyncio.get_running_loop(), q))
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    with _lock:
        for entry in [e for e in _subscribers if e[1] is q]:
            _subscribers.discard(entry)


def _offer(q: asyncio.Queue, kind: str) -> None:
    # Klien lambat cukup kehilangan sinyal: isinya diambil ulang saat ia
    # sempat membaca. Menunggu di sini akan menahan event loop.
    if not q.full():
        q.put_nowait(kind)


def publish(kind: str) -> None:
    """Aman dipanggil dari thread mana pun (handler `def` di threadpool)."""
    with _lock:
        targets = list(_subscribers)
    for loop, q in targets:
        try:
            loop.call_soon_threadsafe(_offer, q, kind)
        except RuntimeError:
            unsubscribe(q)  # loop sudah tertutup
