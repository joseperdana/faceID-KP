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
