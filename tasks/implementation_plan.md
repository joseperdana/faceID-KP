# 🛠️ Implementation Plan: Refactor Absen KP & KP45 Indonesian Photobooth

## 🎯 High-Level Objective
Execute an industrial-grade refactoring of the FaceID-KP attendance kiosk, harden backend security & race conditions, implement fast manual fallback, and construct the KP45 Indonesian Photobooth module for tomorrow's event.

---

## 👥 Subagent Squad Allocation
1. **`attendance_engineer` (Subagent):**
   - Implement TDD test suite for attendance logging & recognition fallback.
   - Refactor `routers/kiosk.py` and `routers/attendance.py` with `checkin_method` tracking (`face` vs `manual`).
   - Create `POST /api/attendance/manual-checkin` endpoint.

2. **`creative_ui_engineer` (Subagent):**
   - Refactor Kiosk UI (`frontend/index.html`, `frontend/js/index.js`) to support fast manual fallback search modal.
   - Build `/photobooth` page (`frontend/photobooth.html`, `frontend/js/photobooth.js`):
     - Camera live stream selection (front/back camera).
     - Indonesian / KP45 theme frames (Merah Putih, Batik Gold, Retro Youth).
     - Real-time HTML5 Canvas composite rendering.
     - 3-second countdown flash effect.
     - High-res image download & preview modal.
   - Link `/photobooth` seamlessly in the navigation bar.

3. **`security_architect` (Subagent):**
   - Audit all API routes, SlowAPI rate limits, and exception handlers.
   - Ensure all DB calls and ML calculations are wrapped with `run_in_threadpool`.
   - Validate XSS prevention on user inputs and sanitize innerHTML rendering.

4. **Orchestrator (Lead Agent):**
   - Coordinate subagents, verify end-to-end integration tests, update dev brain wiki, and generate final commit report.

---

## 🧪 Test-Driven Development (TDD) Strategy
1. **Unit & API Tests (`tests/test_kiosk_and_attendance.py`):**
   - Test recognition endpoint with mock embeddings.
   - Test manual check-in endpoint with duplicate prevention (TOCTOU).
   - Test rate-limiting enforcement on `/api/recognize` and `/api/attendance/manual-checkin`.
   - Test soft-deleted user exclusion.
2. **Frontend Simulation:**
   - Verify photobooth canvas generation on mobile viewport.
   - Verify camera lifecycle cleanup (stop tracks when navigating away).

---

## 📈 Execution Milestones
- [x] **Milestone 1:** Lock & write comprehensive PRD v2.0 in `PRD.md`.
- [ ] **Milestone 2:** Write TDD test suite in `tests/test_kiosk_and_attendance.py`.
- [ ] **Milestone 3:** Backend Refactor — Manual Checkin API & `checkin_method` column handling.
- [ ] **Milestone 4:** Frontend Kiosk Refactor — Fast manual search modal & responsive oval guide.
- [ ] **Milestone 5:** KP45 Indonesian Photobooth Engine — 3 frames, HTML5 canvas renderer, stickers, snapshot & download.
- [ ] **Milestone 6:** Security, Performance & DevBrain Wiki Sync.
