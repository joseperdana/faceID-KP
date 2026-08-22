# Engineering Lessons & Anti-Patterns Log

## 1. Zero-Emoji Design Strictness
- **Issue:** Emojis (e.g. 📍, 📸, ⚠️, ✨, ⚜️) were inadvertently present inside JavaScript DOM mutations and canvas renderers even when HTML templates were sanitized.
- **Rule:** Never insert Unicode emojis directly into JavaScript strings, canvas renders, status badges, or alerts. Always use stroke-aligned inline SVGs or clean monospaced/sans text labels.

## 2. API Contract & Response Mapping Integrity
- **Issue:** Frontend fetch URLs and JSON key lookups diverged from backend FastAPI router schemas (`/api/dashboard/stats` vs `/api/dashboard-stats`, nested vs flat payload keys).
- **Rule:** Always inspect router route definitions and service payload keys directly before writing client-side fetch handlers. Ensure full contract alignment between FastAPI DTOs/services and client consumers.

## 3. End-to-End Test Robustness for Authenticated Flows
- **Issue:** Playwright tests previously only validated that unauthenticated users got redirected, failing to test actual dashboard rendering, data loading, tab switching, and console errors.
- **Rule:** Every authenticated UI page must have an active E2E test verifying full payload rendering, interactive modal operations, tab switches, and zero browser console errors.

## 4. Database Schema Backward Compatibility in Write Operations
- **Issue:** Backend tried to insert `method` into `attendance_logs` table before the column was migrated in PostgreSQL, causing PostgREST error `PGRST204` on every attendance insert.
- **Rule:** Always make DB service insertion methods defensive against schema drift, falling back to verified core columns if newly introduced optional auditing columns are not yet in the target database schema.

## 5. Kiosk Detection & Auto-Capture Threshold Calibration
- **Issue:** Setting `REQUIRED_STABLE_FRAMES` to 45 with a tight movement threshold (0.03) forced users to remain completely still for 3 seconds, causing false auto-capture failures in real-world kiosk environments.
- **Rule:** Keep kiosk stability thresholds responsive (~15 frames / 0.5s, 0.045 movement allowance, 0.45 detection confidence) to accommodate real-world lighting and posture movements.
