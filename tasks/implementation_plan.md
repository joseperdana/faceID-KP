# Implementation Plan: FaceID-KP Refactoring & Improvements

## Phase 1: Security & Architecture Core
1. **Implement JWT-based Authentication:** Replace the static `"rahasia_negara"` cookie token with dynamic JWTs (JSON Web Tokens). Create `core/security.py` for hashing passwords and generating/verifying tokens.
2. **Setup Modular Router Structure (APIRouter):** Break down `main.py` into routers: `routers/auth.py`, `routers/attendance.py`, `routers/users.py`, `routers/analytics.py`, and `routers/pages.py`.
3. **Pydantic Schemas:** Create a `schemas/` directory and define strict Pydantic models for all incoming requests and outgoing responses to ensure type safety.

## Phase 2: ML Pipeline Optimization
1. **Async Event Loop Unblocking:** Use `starlette.concurrency.run_in_threadpool` in FastAPI to run `face_service.get_embedding()` in a separate thread. This prevents CPU-bound inference from blocking concurrent I/O operations.
2. **Error Handling & Model Loading:** Ensure `face_service` handles bad image bytes more gracefully and define a custom exception for AI errors.

## Phase 3: Service Layer Extraction (Demand Elegance)
1. **Analytics Service:** Move all the data processing logic (Pandas Excel generation, heatmap calculations, trend lists) from routing into a dedicated `services/analytics_service.py`.
2. **Database Service:** Abstract Supabase interactions into repository functions (e.g., `services/user_service.py`) rather than calling `supabase.table().select()` directly inside route endpoints. 

## Phase 4: Frontend UI/UX Refinement
1. **Standardize Tailwind CSS:** Remove inline styles (like those in `register.html`). Create a central `static/css/styles.css` file with `@layer components` to define reusable button and input styles, ensuring visual hierarchy.
2. **Component Separation (JS):** Refactor the massive inline `<script>` blocks in `dashboard.html` and `index.html` into external JavaScript files located in `static/js/` to maintain clean HTML.
3. **Geofencing & Security:** Move sensitive geofencing logic validations entirely to the backend. The frontend should just send the coordinates, and the backend validates them to prevent bypass.

## Phase 5: Verification & Testing
1. **Functional Testing:** Verify all endpoints (Login, Register, Dashboard Stats, Excel Export).
2. **RLS Readiness:** Audit database structure and configure Row Level Security on Supabase. Ensure only authenticated admin APIs bypass it if needed, while kiosk modes rely on anonymous keys with restricted insert-only rights.
