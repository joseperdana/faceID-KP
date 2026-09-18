# 🗺️ Implementation Plan: Archify System Visualizations for FaceID-KP

## 1. Overview & Objective
Integrate the **Archify** visual architecture compiler as an agent skill within `.agents/skills/archify/` and generate 3 production-grade, interactive standalone HTML diagrams with 100% showcase-quality validation:
1. **System & Security Architecture (`architecture`)**: Multi-tier boundary mapping Client Web Apps, FastAPI Backend, AI Processing Worker (InsightFace ArcFace), and Supabase BaaS (PostgreSQL + pgvector + Auth + Storage).
2. **Kiosk Face Recognition State Machine (`lifecycle`)**: State flow from video feed tracking, stability thresholding (15 frames), embedding generation, similarity matching, to attendance confirmation and cooldown.
3. **Photobooth 4-Shot Delivery Workflow (`workflow` v2)**: Real-time 4-pose capture, client-side canvas strip compositing, asset upload to Supabase Storage, QR code generation, and landing page retrieval.

---

## 2. Archify Skill Integration
- Target directory: `.agents/skills/archify/`
- Key components to preserve:
  - `bin/archify.mjs` (CLI entry point)
  - `schemas/` (JSON schemas for architecture, workflow, sequence, dataflow, lifecycle)
  - `renderers/` (Deterministic SVG/HTML layout engines)
  - `brand-marks/` (Verified tech brand SVG vectors: FastAPI, Python, PostgreSQL, Supabase, Tailwind, etc.)
  - `SKILL.md` (Agent skill manifest for Antigravity)

---

## 3. Diagram Specification Details

### Diagram 1: `faceid-kp.architecture.json`
- **Type:** `architecture`
- **Preset:** `classic` / `blueprint`
- **Quality Profile:** `showcase`
- **Nodes & Boundaries:**
  - `boundary_client`: Kiosk HUD (`kiosk_web`), Admin Dashboard (`admin_web`), Photobooth Web (`photobooth_web`).
  - `boundary_backend`: FastAPI Gateway (`fastapi_app`), Geofencing Guard (`geo_guard`), Auth & JWT (`auth_module`), Face Router (`face_router`).
  - `boundary_ai`: MediaPipe Client Tracker (`mediapipe_tracker`), Face Service / InsightFace ArcFace (`insightface_service`).
  - `boundary_data`: Supabase PostgreSQL & pgvector (`supabase_db`), Supabase Storage (`supabase_storage`), Supabase Auth (`supabase_auth`).
- **Flows:**
  - Video stream -> MediaPipe tracker -> Base64 Frame POST -> FastAPI Face Router
  - FastAPI -> Face Service (512-d ArcFace embedding extraction)
  - FastAPI -> Supabase RPC `match_faces` (Cosine distance search on 512-d vector)
  - FastAPI -> `attendance_logs` insert with fallback resilience

### Diagram 2: `kiosk-detection.lifecycle.json`
- **Type:** `lifecycle`
- **Quality Profile:** `showcase`
- **Phases:**
  - Column 0 (Idle): `IDLE_WAITING`
  - Column 1 (Detection): `FACE_ACQUIRED`
  - Column 2 (Stability): `STABILITY_SAMPLING` (15 frames, <0.045 movement)
  - Column 3 (Recognition): `EMBEDDING_MATCHING`
  - Column 4 (Outcome): `ATTENDANCE_CONFIRMED`
  - Recoverable/Terminal States: `STABILITY_FAILED`, `UNRECOGNIZED_FACE`, `MANUAL_OVERRIDE`

### Diagram 3: `photobooth-pipeline.workflow.json`
- **Type:** `workflow` (schema v2)
- **Quality Profile:** `showcase`
- **Steps:**
  - Setup & Preset Selection (`KP45` / `Nusantara Light` / `Pesta Merdeka`)
  - 4-Shot Timed Capture Loop (3s countdown per shot)
  - Local Canvas 4-Strip Rendering & Watermarking
  - Multipart Image Upload to `/api/photobooth/upload`
  - Supabase Storage Bucket Persist (`photobooth/strips/`)
  - Public QR Code Render & Mobile Download Screen

---

## 4. Compilation & Verification Plan
1. Validate each candidate using `node .agents/skills/archify/bin/archify.mjs validate <type> <file.json> --quality showcase --json`.
2. Deliver compiled HTML using `node .agents/skills/archify/bin/archify.mjs deliver <type> <file.json> <output.html> --quality showcase --json`.
3. Mount `/docs/diagrams` in FastAPI `main.py` so diagrams are viewable directly at `http://localhost:8000/docs/diagrams/...` and create an index page.
4. Run regression tests with pytest to ensure no existing routes were modified or broken.
