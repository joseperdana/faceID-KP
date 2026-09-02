# 🗺️ Task: Integrate Archify & Generate FaceID-KP System Visualizations

- [x] **1. Skill Installation & Environment Setup**
  - [x] Copy Archify skill package to `.agents/skills/archify/` with full binary, renderers, schemas, and brand assets.
  - [x] Verify `node .agents/skills/archify/bin/archify.mjs doctor` and CLI availability.

- [x] **2. Authoring Typed JSON Specifications for FaceID-KP**
  - [x] Create `docs/diagrams/faceid-kp.architecture.json` (Multi-tier: Kiosk, Photobooth, Admin <-> FastAPI <-> InsightFace AI <-> Supabase pgvector/Storage).
  - [x] Create `docs/diagrams/kiosk-detection.lifecycle.json` (Kiosk Face Stability, AI Extraction, Vector Match, and Confirmation State Machine).
  - [x] Create `docs/diagrams/photobooth-pipeline.workflow.json` (Photobooth 4-shot capture, frame compositing, QR generation, and Supabase Storage pipeline).

- [x] **3. Quality Showcase Validation & Compilation**
  - [x] Run `archify validate` with `--quality showcase` on all 3 specifications (0 errors, 0 warnings).
  - [x] Run `archify deliver` to generate self-contained, interactive HTML artifacts in `docs/diagrams/`.

- [x] **4. Web Serving & Direct Local Access Integration**
  - [x] Mount `docs/diagrams` in FastAPI (`/diagrams/architecture`, `/diagrams/lifecycle`, `/diagrams/workflow`) for instant browser preview during development.
  - [x] Verify HTTP endpoints and static asset serving.

- [x] **5. Verification, QA & Automated Git Management**
  - [x] Run test suite (`pytest tests/test_kiosk_and_attendance.py tests/test_photobooth_api.py -v` -> 10/10 passed).
  - [x] Stage and commit changes to `feature/archify-system-architecture`.
  - [x] Document learning points and direct preview links.
