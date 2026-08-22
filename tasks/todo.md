# 📝 Photobooth Landing Preview, Center Countdown, & Retake Tasks

- [x] **1. Landing Page UI & Camera Preview (`frontend/photobooth.html`)**
  - [x] Embed live camera preview on Welcome Stage
  - [x] Move Time Interval (3s / 5s) selector to Welcome Stage
  - [x] Move Mirror Toggle to Welcome Stage preview
  - [x] Add Center Countdown element (`#center-countdown`) with zero blackout backdrop
  - [x] Add Review & Retake action bar (`#pose-review-overlay`) with 3x retake quota

- [x] **2. Engine & Lifecycle Logic (`frontend/js/photobooth.js`)**
  - [x] Initialize camera immediately on landing page
  - [x] Implement robust 3s / 5s countdown timer without overlapping intervals
  - [x] Implement per-pose retake loop with 3x quota decrement and re-capture
  - [x] Maintain seamless printing animation and modal hierarchy

- [x] **3. Testing & Verification**
  - [x] Update Playwright E2E tests (`tests/test_e2e_playwright.py`) for 3s/5s timers, retake flow, and landing camera preview
  - [x] Verify 100% test passing across Pytest & Playwright (14/14 passed)

