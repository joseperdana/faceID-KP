# 📸 Implementation Plan: Landing Page Camera Preview, Center Countdown, Interval Fix & Retake Engine

## 📌 Requirements Summary
1. **Center Overlay Countdown:** Reposition countdown from top-right to exact center of viewfinder with large, high-contrast typography (`text-9xl md:text-[12rem] text-white drop-shadow-[0_8px_30px_rgba(0,0,0,0.85)]`) while keeping camera preview 100% visible (zero blackout/dark overlay).
2. **Landing Page Revamp (Welcome Stage):**
   - Live Camera Preview right on the landing page so users can check hair/lighting before starting.
   - Time interval selector (3s vs 5s) moved to landing page.
   - Mirror mode toggle moved to landing page.
   - Layout selector (3-strip, 4-strip, 2x2, single) + Custom Message input + "Mulai Foto" button.
3. **Timer Interval Fix & Comprehensive E2E Testing:**
   - Fix timer interval state and countdown lifecycle ensuring 3s and 5s both trigger accurate, monotonic 1000ms ticks.
   - Add automated Playwright tests for both 3s and 5s countdown configurations.
4. **Per-Pose Retake Engine (3x Quota per Session):**
   - After each shot, present a 3.5s review pill with thumbnail:
     - Button: `Retake Pose Ini (Sisa: X)`
     - Button: `Lanjut` (or auto-proceed after 3.5s)
   - If retaken: decrement quota, discard current pose, and re-trigger countdown for the same pose index.

---

## 🛠️ Architecture & Component Breakdown

### A. Landing Page (`frontend/photobooth.html` & `frontend/js/photobooth.js`)
* **Welcome Stage Grid:**
  - Left column (Hero): Live Webcam Viewfinder with mirror toggle and live aspect ratio guide.
  - Right column: Layout Cards (3-Strip, 4-Strip, 2x2 Bento, Single), Time Interval selector (3s / 5s), Custom Message input, and "Mulai Foto" primary button.
* **Camera Capture Stage:**
  - Transition when "Mulai Foto" is clicked.
  - Giant center countdown number (`#center-countdown`).
  - Review / Retake Bar (`#retake-bar`) displayed after each shot with countdown progress ring.

### B. State Management in `photobooth.js`
* `timerDuration` (3 or 5, set on landing page).
* `isMirrored` (toggled on landing page).
* `remainingRetakes` (starts at 3).
* Pose review promise resolution (`retake` vs `proceed`).

---

## 🧪 Testing & Verification
* Playwright E2E:
  - Test landing page camera preview initialization.
  - Test switching time interval (3s & 5s) on landing page.
  - Test mirror toggle.
  - Test center countdown visibility.
  - Test retake button interaction and quota decrement.
* Pytest API suite (13/13 passing).
