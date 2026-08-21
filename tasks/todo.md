# 📋 Master Todo List: Refactor Absen KP & KP45 Indonesian Photobooth

## 🚀 Phase 1: PRD, Architecture & TDD Setup
- [x] Write PRD v2.0 in `PRD.md` with explicit Kiosk, Manual Fallback, and KP45 Photobooth specs
- [x] Write Implementation Plan in `tasks/implementation_plan.md`
- [x] Create pytest test suite `tests/test_kiosk_and_attendance.py` (TDD First)
- [x] Run pytest baseline to confirm test failures (Red phase)

## ⚙️ Phase 2: Backend & Attendance Refactor (`attendance_engineer`)
- [x] Update `routers/kiosk.py` to add `POST /api/attendance/manual-checkin` endpoint
- [x] Add query endpoint `GET /api/users/search?q=` for fast autocomplete in kiosk
- [x] Ensure `checkin_method` (`face` vs `manual`) is stored in `attendance_logs` table
- [x] Run pytest to confirm tests pass (Green phase)

## 🎨 Phase 3: Kiosk UX & Manual Fallback Modal (`creative_ui_engineer`)
- [x] Add *"Cari Nama Manual"* button on `frontend/index.html`
- [x] Implement fast debounce autocomplete search modal in `frontend/js/index.js`
- [x] Update success modal to show streak count, last seen date & method badge cleanly

## 🇮🇩 Phase 4: KP45 Indonesian Photobooth Module (`creative_ui_engineer`)
- [x] Create `frontend/photobooth.html` with responsive mobile/desktop layout
- [x] Implement `frontend/js/photobooth.js` using HTML5 Canvas
  - Camera stream controller (switching front/back camera, mirror toggle)
  - 3 Custom frames: Merah Putih KP45, Batik Heritage Gold, Modern Retro Polaroid
  - 3-second countdown flash animation & synthetic audio shutter
  - Snapshot composition onto high-res canvas (1080x1350)
  - Direct image download & modal preview
- [x] Add Photobooth navigation link to all page headers (`index.html`, `dashboard.html`)
- [x] Serve `/photobooth` route in `routers/pages.py`

## 🔒 Phase 5: Security Hardening & DevBrain Sync (`security_architect`)
- [x] Audit rate limits, CORS, and threadpool offloading (`run_in_threadpool`)
- [x] Update `DEV_BRAIN.md` with ADR-003 and ADR-004
- [x] Final end-to-end integration test (6/6 tests passing)
