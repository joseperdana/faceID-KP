# 📄 Product Requirements Document (PRD) — Production v2.0
**Project Name:** FaceID-KP (KPBromoMalang Hub)  
**Version:** 2.0.0 (Core Engine Stabilization + KP45 Special Event Edition)  
**Target Delivery:** Immediate (Ready for KP45 Event)  
**Philosophy:** Zero-Bullshit, Scalable, Secure, Non-Blocking, High-Elegance.

---

## 1. Executive Summary & Core Objectives
FaceID-KP is an integrated facial-recognition attendance and youth ministry command center for **Komisi Pemuda (KP) GKI Bromo Malang** (70–100 active youths every Saturday at 17:00 WIB, 34 committee members).

### Core Objectives:
1. **Zero-Friction Attendance:** Sub-second (<150ms) facial recognition check-in at church entrance with automatic stability tracking.
2. **Fail-Safe Fallback:** Instant 1-tap manual name search fallback when lighting or face recognition encounters edge cases, ensuring zero queue buildup.
3. **Data Integrity & Auditing:** Real-time sync to Supabase PostgreSQL, separating `checkin_method` (`'face'` vs `'manual'`), with TOCTOU race-condition prevention.
4. **Special Event Feature (KP45 Indonesian Photobooth):** A zero-server-latency, client-side HTML5 Canvas photobooth with custom Indonesian/Batik/Merah-Putih frames and KP45 branding for celebration day, with instant high-res photo download & QR sharing.
5. **Operational Analytics:** Real-time Admin Command Center for committee (Sie Pemerhati) to monitor live attendance, gender ratios, newcomer identification, and retention alerts.

---

## 2. User Roles & Permission Matrix (RBAC)

| Role | Access Scope | Capabilities |
| :--- | :--- | :--- |
| **Public / Jemaat** | `/`, `/photobooth`, `/register` | Attendance check-in (Face/Manual), KP45 Photobooth capture, Newcomer face registration. |
| **Kiosk Device** | `/` (or dedicated tablet) | Auto-scanning loop, auto-reset modal (3.5s), offline resilient fallback. |
| **Pengurus / Admin** | `/dashboard`, `/login`, `/api/admin/*` | View analytics, export CSV/Excel, manage users (soft delete), attendance audit log, real-time feed. |

---

## 3. Scope & Non-Goals

### In Scope (v2.0):
* ✅ **FaceID Attendance Kiosk (`/`):** MediaPipe landmark detection + server-side Cosine Similarity matching with GPS geofence filter (200m).
* ✅ **Fast Manual Fallback:** Live autocomplete search modal on kiosk for panitia/jemaat manual check-in with audit logging.
* ✅ **Newcomer Fast Registration (`/register`):** Single-page photo capture + name + phone number + gender onboarding.
* ✅ **Admin Command Center (`/dashboard`):** Heatmaps, gender breakdown, newcomer highlight, retention monitoring (at-risk alerts), export data.
* ✅ **KP45 Indonesian Photobooth (`/photobooth`):** Interactive canvas photobooth with 3+ Indonesia/KP45 frames, countdown timer, filter controls, sticker stamps, and instant JPEG export.
* ✅ **Backend Hardening:** Non-blocking async endpoints (`run_in_threadpool`), SlowAPI rate limiting, input sanitization against XSS, and SQL constraints.

### Out of Scope (Explicitly Deferred to v3.0):
* ❌ Public Profile CMS / Marketing Landing Page.
* ❌ Individual Jemaat Login / Personal Streak Portal.
* ❌ Automated WhatsApp Gateway notifications.
* ❌ AI Sentiment / Emotion Analysis.

---

## 4. End-to-End User Journeys

### Journey A: Facial Recognition Check-In
1. Jemaat stands in front of Kiosk camera within oval guide.
2. MediaPipe detects nose landmark stability (45 frames within safe zone).
3. Frame is captured and sent via `POST /api/recognize` with GPS coordinates.
4. Server extracts embedding, computes Cosine Similarity with registered faces (`threshold >= 0.70`).
5. **Success:** Returns Jemaat Name, Streak Count, Last Seen. Success modal displays for 3.5s with progress countdown and automatically resets.
6. **Unknown / Error:** Prompts 1-tap retry, manual search button, or new member registration link.

### Journey B: Fast Manual Fallback Check-In
1. If scan fails or lighting is poor, user taps *"Cari Nama Manual"*.
2. Modal opens with instant search bar filtering active members.
3. User selects name -> triggers `POST /api/attendance/manual-checkin`.
4. System logs attendance with `checkin_method = 'manual'` and displays success modal.

### Journey C: KP45 Indonesian Photobooth
1. User accesses `/photobooth` on mobile or photo station.
2. Selects Indonesian/KP45 Frame:
   - Frame 1: *Dirgahayu RI & KP45 Merah Putih*
   - Frame 2: *Batik Heritage & GKI Bromo Gold*
   - Frame 3: *Modern Youth Retro Polaroid*
3. Camera live preview inside frame with 3s/5s countdown timer.
4. Canvas renders composite high-res image (video snapshot + chosen frame overlay + date stamp).
5. User can download high-res JPEG directly or scan local QR code.

---

## 5. Technical Architecture & Tech Stack

```
[ Frontend: Vanilla JS + Tailwind CSS + HTML5 Canvas + MediaPipe ]
                       │
             HTTPS REST JSON API
                       │
[ Backend: FastAPI (Python 3.10+) with SlowAPI Rate Limiting ]
      ├── /api/recognize (Async ThreadPool MediaPipe + Vector Math)
      ├── /api/attendance/* (Attendance Logging & TOCTOU Safeguard)
      ├── /api/users/* (Registration & Management)
      └── /api/admin/* (Protected Analytics & Audit Feed)
                       │
         Supabase Client / PostgREST
                       │
[ BaaS Database: Supabase PostgreSQL ]
      ├── table: users (id, name, phone, gender, embedding, is_deleted, created_at)
      ├── table: attendance_logs (id, user_id, date, timestamp, method, device_info)
      └── UNIQUE constraint on (user_id, date)
```

---

## 6. Non-Functional Requirements (NFR)
1. **Latency:** Facial recognition response time `< 150ms` (P95).
2. **Concurrency:** Handles 100 requests in 15 minutes without thread starvation.
3. **Resilience:** Kiosk must gracefully handle temporary network glitches without freezing the camera stream.
4. **Security:** JWT authentication for dashboard routes, rate limiting on sensitive endpoints, strict CORS policy, and zero client-side service keys.

---

## 7. Acceptance Criteria & Definition of Done (DoD)
- [ ] PRD approved and locked.
- [ ] Unit & integration tests pass with `pytest` (TDD verification).
- [ ] Kiosk recognition works seamlessly with auto-reset.
- [ ] Manual check-in modal works and correctly logs `method: manual`.
- [ ] KP45 Indonesian Photobooth operates smoothly on both desktop and mobile browsers.
- [ ] Security audit passes: Rate limiting active, XSS sanitized, TOCTOU prevented.
