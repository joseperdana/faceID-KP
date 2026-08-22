# 📝 Kiosk Face Recognition & Manual Attendance Reliability (Sandbox Fix)

- [x] **1. Root Cause Resolution in Database Service (`services/db_service.py`)**
  - [x] Update `DBService.insert_log` to safely handle schema without crashing on missing `method` column (PGRST204 fix).
  - [x] Optimize `DBService.match_faces` default threshold from 0.50 to 0.42 for robust face recall across lighting/angle variations.
  - [x] Enhance `DBService.search_active_users` to query both `full_name` and `phone_number` with an expanded limit (25) and whitespace sanitization.

- [x] **2. Kiosk Frontend Detection & Responsiveness Tuning (`frontend/js/index.js`)**
  - [x] Tune `REQUIRED_STABLE_FRAMES` from 45 down to 15 (~0.5s) so users don't have to freeze for 3s.
  - [x] Tune `MOVEMENT_THRESHOLD` from 0.03 to 0.045 to prevent micro-movements (breathing, blinks) from resetting progress.
  - [x] Adjust MediaPipe `minDetectionConfidence` from 0.6 to 0.45 for reliable detection in warm/dim ambient church lighting.
  - [x] Broaden safe zone bounds (X: 0.20–0.80, Y: 0.15–0.85).

- [x] **3. Backend Error Handling & Audit Integrity (`routers/kiosk.py`)**
  - [x] Ensure `manual_checkin` and `recognize` gracefully return meaningful error payloads if DB errors occur.
  - [x] Protect timestamp parsing in last_seen calculations against edge cases.

- [x] **4. Comprehensive TDD & Sandbox Verification (`tests/`)**
  - [x] Add unit tests for DB resilience with/without `method` column.
  - [x] Add tests for multi-field user search (`phone_number` and `full_name`).
  - [x] Run full Pytest test suite (`pytest tests/ -v` -> 16/16 passed).
  - [x] Run live sandbox integration test against real Supabase instance.
