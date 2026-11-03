"""Uji beban tanya jawab: N HP mengirim satu pertanyaan lalu polling daftar.

Pakai (saat gladi, flag qna MENYALA, sesi DIBUKA, mode upvote):
    venv/bin/python scripts/qna_loadtest.py https://<domain-web-kp> --devices 130 --minutes 5
Kiriman disebar dalam 3 menit (< 60/menit, batas per IP), karena skrip ini
berjalan dari satu IP, sama seperti satu WiFi gereja.

Bersihkan sesudahnya di SQL Editor:
    delete from qna_questions where body like '[LOADTEST]%';
Keluar dengan kode 1 kalau p95 > 500 ms atau ada error.
"""
import argparse
import asyncio
import random
import statistics
import time
import uuid

import httpx

SUBMIT_SPREAD_S = 180


async def device(client, base, deadline, latencies, errors):
    dev = str(uuid.uuid4())
    await asyncio.sleep(random.uniform(0, SUBMIT_SPREAD_S))  # noqa: S311 — jitter beban, bukan kriptografi
    started = time.perf_counter()
    try:
        res = await client.post(f"{base}/api/qna/questions",
                                json={"body": f"[LOADTEST] pertanyaan {dev[:8]}", "device_id": dev})
        if res.status_code != 200:
            errors.append(("submit", res.status_code))
    except httpx.HTTPError as e:
        errors.append(("submit", type(e).__name__))
    latencies.append(time.perf_counter() - started)
    while time.monotonic() < deadline:
        started = time.perf_counter()
        try:
            res = await client.get(f"{base}/api/qna/questions/public", params={"device_id": dev})
            if res.status_code != 200:
                errors.append(("list", res.status_code))
        except httpx.HTTPError as e:
            errors.append(("list", type(e).__name__))
        latencies.append(time.perf_counter() - started)
        await asyncio.sleep(5 + random.uniform(-0.5, 0.5))  # noqa: S311 — jitter beban


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--devices", type=int, default=130)
    parser.add_argument("--minutes", type=float, default=5)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    deadline = time.monotonic() + args.minutes * 60
    latencies, errors = [], []
    limits = httpx.Limits(max_connections=args.devices)
    async with httpx.AsyncClient(timeout=10, limits=limits) as client:
        await asyncio.gather(*(device(client, base, deadline, latencies, errors) for _ in range(args.devices)))
    p50 = statistics.median(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000
    print(f"request: {len(latencies)}  p50: {p50:.0f} ms  p95: {p95:.0f} ms  error: {len(errors)}")
    if errors:
        print("contoh error:", errors[:10])
    raise SystemExit(1 if errors or p95 > 500 else 0)


if __name__ == "__main__":
    asyncio.run(main())
