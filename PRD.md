# 📄 Product Requirements Document (PRD) — Production v2.0
**Project Name:** FaceID-KP (KPBromoMalang Hub)  
**Version:** 2.1.0 (Post-Audit Hardening)
**Last verified against code:** 2026-09-09 — see `tasks/AUDIT_2026-09-08.md`  
**Target Delivery:** Immediate (Ready for KP45 Event)  
**Philosophy:** Zero-Bullshit, Scalable, Secure, Non-Blocking, High-Elegance.

---

## 1. Executive Summary & Core Objectives
FaceID-KP is an integrated facial-recognition attendance and youth ministry command center for **Komisi Pemuda (KP) GKI Bromo Malang** (70–100 active youths every Saturday at 17:00 WIB, 34 committee members).

### Core Objectives:
1. **Zero-Friction Attendance:** Facial recognition check-in at the church entrance with automatic stability tracking. See §6 for the measured latency budget — the previously stated <150 ms was never measured and is not achievable on the target hardware.
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
* ✅ **FaceID Attendance Kiosk (`/`):** MediaPipe (in-browser stability detection only) + **InsightFace `buffalo_l`** server-side embedding, matched with pgvector cosine distance. GPS geofence filter (200 m default) — see §9 for what that control can and cannot do.
* ✅ **Fast Manual Fallback:** Live autocomplete search modal on kiosk for panitia/jemaat manual check-in with audit logging.
* ✅ **Newcomer Fast Registration (`/register`):** Single-page photo capture + name + phone number + gender onboarding.
* ✅ **Admin Command Center (`/dashboard`):** Heatmaps, gender breakdown, newcomer highlight, retention monitoring (at-risk alerts), export data.
* ✅ **KP45 Indonesian Photobooth (`/photobooth`):** Interactive canvas photobooth with 3+ Indonesia/KP45 frames, countdown timer, filter controls, sticker stamps, and instant JPEG export.
* ✅ **Backend Hardening:** Non-blocking endpoints (`run_in_threadpool`), a single shared SlowAPI limiter, input sanitisation, upload validation (count/size/magic bytes), and the database constraints in `migrations/001_init.sql`.

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
4. Server extracts an embedding and calls `match_faces` (pgvector, cosine distance) for the two nearest candidates.
   * `FACE_MATCH_THRESHOLD` (default **0.42**) is the minimum similarity for a match.
   * `FACE_MATCH_MARGIN` (default 0.05) is the minimum gap to the runner-up; below it the scan is reported as `ambiguous` and the member is sent to manual search rather than a name being guessed.
   * `FACE_DUPLICATE_THRESHOLD` (default 0.35) gates registration and **must be lower than** the match threshold — see §8.
5. **Success:** Returns `status: "success"` with name, attendance count and last seen. The success modal displays for 3.5 s and resets automatically.
5b. **Already checked in:** Returns `status: "already_checked_in"`, rendered as a distinct amber panel showing the original check-in time. This must never be presented as a fresh check-in.
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

1. **Latency.** The earlier target of `< 150 ms P95` was never measured and is not
   reachable on the target hardware (1 vCPU, 2 GB). Estimated budget for a single
   recognition on that box:

   | Stage | Estimate |
   | :--- | ---: |
   | Upload (640 px JPEG q0.82, ~35 KB) | 40–200 ms |
   | Image decode | 8–15 ms |
   | Detection `det_10g` @ 640² | 400–900 ms |
   | Embedding `w600k_r50` | 400–800 ms |
   | Supabase round trips (2, was 4) | 80–160 ms |
   | **Total server-side** | **~0.9–2.1 s** |

   **Target: < 2.5 s P95 end-to-end.** This number is an estimate from code and
   hardware, not a measurement. Before quoting it anywhere, run a benchmark
   against the real VPS and replace it with the measured figure. An NFR that has
   never been measured is not an NFR.

   Cost levers, in order of effect: `FACE_DET_SIZE=320` (roughly quarters
   detection cost), `FACE_MODEL_NAME=buffalo_sc`, and the client-side downscale
   already applied in `frontend/js/index.js`.

2. **Concurrency.** 100 check-ins within a 45-minute window. On one vCPU
   inference is effectively serial, so the practical ceiling is roughly one scan
   per 1–2 s. Rate limits are set well above the expected arrival rate
   (`RATE_LIMIT_RECOGNIZE=240/minute`) because they are keyed per client and a
   burst of arrivals is normal.

3. **Resilience.** The kiosk must remain usable when any single dependency fails:
   * CDN unreachable → manual search still works (the fallback UI is bound before
     any CDN-dependent code runs).
   * Camera denied or busy → an explicit message plus manual search.
   * Face model unloadable → the app still boots; recognition returns 503 and the
     kiosk falls back to manual search.
   * Server unreachable → the automatic retry loop stops after three consecutive
     failures instead of firing at a dead server for the rest of the service.

4. **Security.** JWT sessions (HS256, 8 h) over HTTPS with `Secure` +
   `SameSite=strict` cookies; bcrypt-hashed admin password; kiosk-scope endpoints
   gated by an enrolled device token; CSP, HSTS and frame-ancestors headers;
   Supabase RLS enabled with `anon` access revoked.

## 7bis. Data Protection (UU 27/2022)

Face embeddings are **data pribadi spesifik** under Article 4(2), which requires
explicit, standalone consent.

* Registration refuses to proceed without a ticked consent box; `consent_at` and
  `consent_version` are stored on the member record.
* Members under 18 require a guardian present — stated on the registration form.
* Archiving a member (`DELETE /api/users/{id}`) hides them and **keeps** their
  face data, and the UI says so.
* Erasure (`DELETE /api/users/{id}/biometrics`) nulls `face_embedding` and
  `phone_number` irreversibly. This is the action that answers a deletion
  request. Attendance history is retained; it carries no biometric data.
* Retention: review annually and purge biometrics for members inactive over
  12 months.

## 8. Recognition thresholds — why the ordering matters

`FACE_DUPLICATE_THRESHOLD` **must be ≤ `FACE_MATCH_THRESHOLD`**; `core/config.py`
refuses to start otherwise.

When registration used 0.5 while recognition used 0.42, similarities between
those two values formed a dead zone: a new face similar at 0.45 passed the
duplicate check as "a different person", and was then matched to that existing
member at every subsequent check-in. Attendance was logged under the wrong name,
weekly, with no audit trail. In a congregation with siblings this is not
hypothetical.

## 9. Geofencing — what it is for

`lat`/`lng` are two numbers supplied by the browser. The server cannot verify
them, and the church coordinates are in this repository.

* **It does:** stop accidental check-ins from home by honest users, and give a
  clear message when someone is plainly elsewhere.
* **It does not:** prove physical presence, or resist anyone who wants to spoof a
  location. Chrome DevTools is sufficient. Do not describe it as a security
  control.
* Poor indoor GPS is handled by rejecting only when the distance exceeds the
  radius by more than the fix's own accuracy — otherwise a wifi-derived fix would
  turn away a member standing at the kiosk.
* `CHURCH_LAT`/`CHURCH_LNG` have **no default** and must be verified on a map.
  This repository previously carried two hardcoded pairs about 965 m apart, so
  neither could be trusted.

## 10. Acceptance Criteria & Definition of Done (DoD)

Measurable, so "done" is checkable rather than a matter of opinion.

- [ ] `pytest tests/` passes, including the auth matrix in
      `tests/test_auth_matrix.py` and the WIB day-boundary tests.
- [ ] `ruff check .` and `node scripts/check_theme_tokens.js` pass.
- [ ] `migrations/001_init.sql` has been applied; `unique_user_per_day` exists and
      RLS is enabled on both tables.
- [ ] A member who checks in twice in one WIB day sees the amber
      "sudah absen" panel, and exactly one attendance row exists.
- [ ] With the CDN blocked, the kiosk's manual search still opens and completes a
      check-in.
- [ ] Registration cannot be submitted without consent, and the stored record has
      a non-null `consent_at`.
- [ ] `DELETE /api/users/{id}/biometrics` leaves `face_embedding` null.
- [ ] Deploy on a clean VPS reaches a green `/healthz`, or fails with a message
      naming what is missing — never a false success.
- [ ] Measured P95 for `/api/recognize` recorded against the real VPS and written
      into §6, replacing the estimate.
- [ ] Face-ID versus manual ratio visible on the dashboard for the last four
      services, as the input to the open question in §11.

## 11. Open question: is face recognition the right mechanism?

The manual fallback is a complete attendance system on its own. Typing three
letters and tapping a name takes roughly 5–8 s. The face path takes roughly the
same, with far more failure modes, a 2 GB VPS, an HTTPS requirement, and the
biometric-data obligations in §7bis — none of which a tap-list carries. A
tap-list also parallelises across three tablets with no code change; one kiosk
does not.

**Proposed test:** run one service with a tap-list only and one with the kiosk.
Compare queue time and success rate. The Face-ID-versus-manual ratio card gives
the ongoing measurement. If the tap-list wins or draws, demote face recognition
to optional.
