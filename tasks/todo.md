# 📝 Photobooth Photo Strip & QR Delivery Task List

- [x] **1. Backend Architecture (`routers/photobooth.py` & `main.py`)**
  - [x] Implement `POST /api/photobooth/upload` with short UUID generation, safe file writing, and LAN IP detection
  - [x] Implement `GET /p/{photo_id}` mobile landing page for instant 1-tap download
  - [x] Register photobooth router in `main.py`
  - [x] Ensure directory `frontend/uploads/photobooth/` exists and is properly served

- [x] **2. Frontend Multi-Pose Engine & Themes (`frontend/photobooth.html` & `frontend/js/photobooth.js`)**
  - [x] Implement 3-Pose automated burst capture sequence with synthesized sound effects and flash
  - [x] Build Canvas Vertical Strip Compositor (1000x3000px 3-pose layout with center-crop aspect ratio safety)
  - [x] Design 4 distinct themes: Merah Putih Cute Fest (17an), Batik Pop Kawaii, Retro Kodachrome 1945, and Obsidian Cyber Minimalist
  - [x] Implement instant SVG QR Code generator and presentation modal
  - [x] Add 45-second auto-reset timer for kiosk queue flow

- [x] **3. Quality Assurance & Anti-Emoji Strictness**
  - [x] Run automated unicode check to guarantee 0 emojis in all JS/HTML code
  - [x] Add pytest unit tests for upload and mobile view endpoints (`tests/test_photobooth_api.py`)
  - [x] Add Playwright E2E test for photobooth capture flow and QR generation (`tests/test_e2e_playwright.py`)
  - [x] Verify 100% test coverage (`13/13 passed`)

- [x] **4. Automated Git Pipeline & Deployment Gate**
  - [x] Create & switch to `feature/photobooth-strip-qr` branch
  - [x] Stage, commit with Conventional Commits (`feat(photobooth): ...`), and merge to `dev`
  - [x] Push to `origin/dev` and update PR to `staging`
  - [x] Provide localhost & LAN test links
