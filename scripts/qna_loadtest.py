"""Uji beban tanya jawab: N HP mengirim satu pertanyaan lalu polling daftar dan status.

Pakai (saat gladi, flag qna MENYALA, mode upvote dipilih SAAT SESI MASIH TUTUP,
lalu sesi DIBUKA):
    venv/bin/python scripts/qna_loadtest.py https://<domain-web-kp> --devices 130 --minutes 5
Urutan penting: mode poin tidak bisa diganti saat sesi terbuka (mode_locked).

Kiriman disebar merata: device ke-i mengirim pada i * spread / devices detik,
dengan spread minimal 180 detik, sehingga laju kiriman tetap di bawah 250/menit
(batas per IP 300/menit). Skrip ini berjalan dari satu IP, sama seperti satu
WiFi gereja. Setiap device juga mem-polling daftar tiap 5 detik dan status
tiap 10 detik, meniru jemaat.js.

Bersihkan sesudahnya di SQL Editor (hanya di gladi, lihat runbook):
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
MAX_SUBMITS_PER_MIN = 250


async def timed_get(client, url, params, kind, latencies, errors):
    started = time.perf_counter()
    try:
        res = await client.get(url, params=params)
        if res.status_code != 200:
            errors.append((kind, res.status_code))
    except httpx.HTTPError as e:
        errors.append((kind, type(e).__name__))
    latencies.append(time.perf_counter() - started)


async def device(client, base, deadline, latencies, errors, index, spread, devices):
    dev = str(uuid.uuid4())
    await asyncio.sleep(index * spread / devices)
    started = time.perf_counter()
    try:
        res = await client.post(f"{base}/api/qna/questions",
                                json={"body": f"[LOADTEST] pertanyaan {dev[:8]}", "device_id": dev})
        if res.status_code != 200:
            errors.append(("submit", res.status_code))
    except httpx.HTTPError as e:
        errors.append(("submit", type(e).__name__))
    latencies.append(time.perf_counter() - started)
    tick = 0
    while time.monotonic() < deadline:
        await timed_get(client, f"{base}/api/qna/questions/public", {"device_id": dev},
                        "list", latencies, errors)
        if tick % 2 == 0:  # status tiap 10 detik (list tiap 5 detik)
            await timed_get(client, f"{base}/api/qna/state", None, "state", latencies, errors)
        tick += 1
        await asyncio.sleep(5 + random.uniform(-0.5, 0.5))  # noqa: S311 — jitter beban


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--devices", type=int, default=130)
    parser.add_argument("--minutes", type=float, default=5)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    spread = max(SUBMIT_SPREAD_S, args.devices * 60 / MAX_SUBMITS_PER_MIN)
    if args.minutes * 60 < spread:
        print(f"peringatan: durasi {args.minutes} menit lebih pendek dari sebaran kiriman "
              f"{spread:.0f} detik; sebagian kiriman akan jatuh setelah batas waktu.")
    deadline = time.monotonic() + args.minutes * 60
    latencies, errors = [], []
    limits = httpx.Limits(max_connections=args.devices)
    async with httpx.AsyncClient(timeout=10, limits=limits) as client:
        await asyncio.gather(*(device(client, base, deadline, latencies, errors, i, spread, args.devices)
                               for i in range(args.devices)))
    p50 = statistics.median(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000
    print(f"request: {len(latencies)}  p50: {p50:.0f} ms  p95: {p95:.0f} ms  error: {len(errors)}")
    if errors:
        print("contoh error:", errors[:10])
    raise SystemExit(1 if errors or p95 > 500 else 0)


if __name__ == "__main__":
    asyncio.run(main())
