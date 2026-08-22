# 📝 Nusantara Festive Light Photobooth Task List

- [x] **1. Setup Asset Directory & 17an Starter Pack**
  - [x] Create directories `frontend/assets/photobooth/stickers/` and `frontend/assets/photobooth/frames/`
  - [x] Generate starter SVG assets (`lencana-dirgahayu.svg`, `pita-merah-putih.svg`, `bintang-nusantara.svg`, `batik-kawung-corner.svg`, `stempel-17an.svg`)

- [x] **2. Frontend Architecture & Flow (`frontend/photobooth.html`)**
  - [x] Implement Light Mode "Nusantara Festive Light" design system (Warm Ivory `#FAF7F2`, Charcoal `#1E1B18`, Terracotta, Gold)
  - [x] Build Welcome Screen with 4 Layout Selection Cards (*3-Strip Vertikal, 4-Strip Vertikal, 2x2 Bento Grid, Single Wide*)
  - [x] Build Crystal Clear Camera Viewfinder (Floating countdown pill, zero dark overlay blackout)
  - [x] Build Skeuomorphic "Printer Slide-Out" animation container
  - [x] Build Result Modal with Dual View (Static Strip + Looping Animated GIF) and prominent QR Code

- [x] **3. Canvas Compositor, GIF Encoder, & Audio Engine (`frontend/js/photobooth.js`)**
  - [x] Integrate `gifshot.min.js` for instant 3-4 frame stop-motion GIF
  - [x] Implement layout rendering algorithms for 3-Strip (1000x3000px), 4-Strip (1000x3400px), 2x2 Bento (2000x2100px), and Single Wide (1600x1900px)
  - [x] Implement mechanical printing animation + paper slide audio synthesis
  - [x] Implement 45s auto-reset countdown timer

- [x] **4. Backend API & Mobile Landing Page (`routers/photobooth.py`)**
  - [x] Support dual upload for static Photo Strip and Animated GIF (`/api/photobooth/upload`)
  - [x] Update mobile landing page (`/p/{id}`) in warm light theme with tabs to download static photo strip and animated GIF

- [x] **5. QA Gate & TDD E2E Test Suite**
  - [x] Verify 0 residual emojis across all files
  - [x] Update unit tests (`tests/test_photobooth_api.py`)
  - [x] Update Playwright E2E tests (`tests/test_e2e_playwright.py`)
  - [x] 100% test pass verification (`13/13 passed`)

- [x] **6. Automated Git Pipeline**
  - [x] Create branch `feature/photobooth-nusantara-light`
  - [x] Commit with Conventional Commits, merge into `dev`, and push to `origin/dev`
  - [x] Create/update PR to `staging`
  - [x] Report localhost & LAN URLs
