# Todo List: System Audit Fixes (Audit Report — July 2026)

## ✅ Previous Work (Completed)
All Phase 1–5 items from prior refactoring are complete.

---

## 🔴 Part 1: Security Hardening (B3)
- [x] Remove hardcoded fallback secret key in `core/security.py` — fail loudly on missing env var
- [x] Move Sentry DSN to environment variable in `main.py`
- [x] Add `slowapi` to `requirements.txt` for rate limiting
- [x] Add rate limiting: 5/min on `/api/login`, 30/min on `/api/recognize`
- [x] Make geofence lat/lng mandatory (remove `Optional`) in `kiosk.py`

## 🔴 Part 2: Race Condition Fix — TOCTOU (B1)
- [x] Provide SQL migration for UNIQUE constraint on `attendance_logs(user_id, date)`
- [x] Refactor `kiosk.py` `/recognize` — replace full history fetch with targeted `check_user_log_today`
- [x] Wrap `insert_log` in try/except to catch DB-level duplicate constraint (code `23505`)

## 🟠 Part 3: XSS + Soft Delete (U3)
- [x] Provide SQL migration for `is_deleted` + `deleted_at` columns on `users` table
- [x] Update `db_service.py`: add `soft_delete_user()`, filter `is_deleted=false` on all user queries
- [x] Update `users.py` router: call `soft_delete_user` instead of hard delete
- [x] Fix `dashboard.html` innerHTML injection — add a `sanitize()` helper to escape user-provided strings

## 🔴 Part 4: Stop Blocking the Async Event Loop (B2)
- [x] Wrap all synchronous DB calls in `kiosk.py` with `run_in_threadpool`
- [x] Add 30-second in-memory TTL cache for `dashboard-stats` endpoint
- [x] Wrap DB calls in `analytics.py` route with `run_in_threadpool`

## 🟠 Part 5: UX Restructure (U1 + U2)
- [x] Restructure Analytics tab: promote At-Risk panel to top, demote leaderboard
- [x] Replace fake `● Live` badge with a `Last Updated` timestamp
- [x] Add `setInterval` auto-refresh (every 30s) for the Overview feed
- [x] Increase recent logs limit from 5 to 15

---

## Git Checkpoints
- After Part 1: `fix/security-hardening`
- After Part 2: `fix/race-condition-toctou`
- After Part 3: `fix/xss-soft-delete`
- After Part 4: `fix/async-db-refactor`
- After Part 5: `fix/ux-restructure`
