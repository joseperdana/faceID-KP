# FaceID-KP (KPBromoMalang Hub) — Smart Attendance & Youth Ministry Command Center

FastAPI (Python) backend + Vanilla JS/Tailwind/HTML5 Canvas frontend. Facial recognition attendance kiosk untuk Komisi Pemuda GKI Bromo Malang (70-130 anggota, ibadah Sabtu 17:00 WIB). AI: InsightFace (ArcFace). DB: Supabase (PostgreSQL + pgvector). Deployment: VPS Ubuntu 24.04.

## Domain constraint penting (tidak bisa diturunkan dari kode)

- **Sub-second check-in**: target <150ms untuk face recognition, dengan stability tracking (45 frame di safe zone sebelum capture) — ini bukan angka arbitrer, ini requirement UX inti supaya antrian 70-100 orang tidak menumpuk di jendela waktu sempit (16:30-17:15 WIB).
- **GPS geofence**: radius 200m dari lokasi gereja, mencegah check-in remote/palsu.
- **Cosine similarity threshold ≥0.70** untuk match wajah; di bawah itu → fallback ke manual search (jangan pernah blok user, selalu ada jalur keluar 1-tap).
- **`checkin_method` wajib dipisah** (`'face'` vs `'manual'`) untuk audit integrity — jangan digabung jadi satu kolom generik.
- **TOCTOU race-condition prevention** wajib untuk operasi check-in konkuren (banyak orang check-in hampir bersamaan saat jam sibuk).
- **KP45 Photobooth** (`/photobooth`) harus **zero-server-latency** — rendering composite image 100% client-side HTML5 Canvas, jangan roundtrip ke server untuk compositing.
- **Non-Goals eksplisit v2.0** (jangan bangun ini kecuali diminta ulang): Public Profile CMS, individual login jemaat, WhatsApp gateway otomatis, AI sentiment analysis.

## Design system — Fluid Clarity

Deep Obsidian `#06070A`, Electric Azure `#2563EB`, Luminous Cyan `#38BDF8`, Emerald `#10B981` (positif/growth), Rose `#F43F5E` (alert/photobooth accent). Font: Plus Jakarta Sans (display), JetBrains Mono (angka metrik/badge). Standar wajib: anti-AI-slop, nol emoji di UI, SVG icon stroke-aligned, kontras WCAG tinggi — lihat skill `anti-ai-slop-design`.

Detail layar & alur lengkap: [KIOSK_SPEC.md](KIOSK_SPEC.md) (kiosk absensi) dan [DASHBOARD_SPEC.md](DASHBOARD_SPEC.md) (admin command center untuk 34 pengurus + tim Pemerhati/at-risk monitoring).

## Keamanan (dari main.py & core/security.py)

Rate limiting via SlowAPI, Sentry error tracking (DSN dari `.env`, jangan hardcode), endpoint async non-blocking (`run_in_threadpool` untuk kerja berat), sanitasi input terhadap XSS, SQL constraint. Endpoint `/api/*` yang unauthorized harus balas JSON 401, bukan redirect — beda dari halaman biasa yang redirect ke `/login`.

## Struktur kode
`routers/` — `pages`, `auth`, `kiosk`, `users`, `analytics`, `attendance`, `photobooth` (satu file per domain, ikuti pola ini untuk endpoint baru). `frontend/` — HTML statis per halaman (`index`=kiosk, `dashboard`, `login`, `photobooth`, `register`) + `js/` + `assets/`. `core/security.py` — helper auth/keamanan bersama.

## Referensi
[PRD.md](PRD.md) — requirement lengkap v2.0, [DESIGN.md](DESIGN.md), [KPContext.md](KPContext.md) — konteks organisasi KP, [GEMINI.md](GEMINI.md) — instruksi lama era Antigravity (diarsipkan, sudah digantikan file ini).
