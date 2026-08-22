# 📝 Superpower Photobooth Revamp Todo List

- [x] **1. Design Tokens & Styling Architecture (`frontend/photobooth.html`)**
  - [x] Implement Neo-Brutalist tactile card styles with solid 4px/6px drop shadows and responsive bento grid
  - [x] Implement playful tilted sticker badges (`-rotate-2`, `rotate-3`, bright contrast colors)
  - [x] Apply `anti-ai-slop-indonesian-writing` to all headings, helper texts, and button copy
  - [x] Add 4 rich theme cards (*Merah Putih Festive 17an, Y2K Photomatix Seoul, Nusantara Modern Batik, Retro Kodachrome 1945*)

- [x] **2. Canvas Compositor & Multi-Pose Engine (`frontend/js/photobooth.js`)**
  - [x] Implement 3-Pose automated burst loop with synthesized Web Audio beeps and realistic mechanical shutter sounds
  - [x] Build high-resolution (1000x3000px, 300 DPI) canvas rendering for:
    - [x] Merah Putih Festive: Warm cream paper, red borders, sticker stars, and Dirgahayu stamp
    - [x] Y2K Photomatix: Soft pastel gradient, doodle stars, Korean/Y2K sticker typography, minimal barcode
    - [x] Nusantara Heritage: Latte kraft paper, gold geometric batik corner ornaments, traditional stamp
    - [x] Retro Kodachrome: Authentic analog film strip with side sprocket holes, ISO 400 marks, frame numbers
  - [x] Center-crop (4:3 ratio) camera framing to prevent portrait distortion
  - [x] Instant SVG QR Code generator with prominent "Scan Buat Simpan" visual card
  - [x] 45-second auto-reset countdown for kiosk queue flow

- [x] **3. Backend & Mobile Landing Page (`routers/photobooth.py`)**
  - [x] Support base64 JPEG upload with short UUID and LAN IP QR link resolution
  - [x] Render mobile download landing page (`/p/{id}`) with tactile Neo-brutalist buttons and Web Share API

- [x] **4. Quality Assurance & TDD Suite**
  - [x] Ensure 0 unicode emojis across all `.html` and `.js` files
  - [x] Write unit & integration tests (`tests/test_photobooth_api.py`)
  - [x] Write Playwright E2E tests for interactive controls and modal lifecycle (`tests/test_e2e_playwright.py`)
  - [x] Verify 100% green tests (`13/13 passed`)

- [x] **5. Automated Git Pipeline**
  - [x] Commit with Conventional Commits on `feature/photobooth-superpower-revamp`
  - [x] Merge to `dev`, push to `origin/dev`, and update/create PR to `staging`
  - [x] Report localhost & LAN test links to user
