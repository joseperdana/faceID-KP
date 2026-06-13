# Todo List: FaceID-KP Refactoring

## Phase 1: Security & Architecture Core
- [x] Create `core/security.py` and implement JWT token generation and verification.
- [x] Refactor `check_admin_auth` dependency to use the new JWT logic.
- [x] Create `schemas/` directory and define Pydantic models for API requests/responses.
- [x] Refactor `main.py` by extracting endpoints into `routers/` (e.g., auth, users, analytics).

## Phase 2: ML Pipeline Optimization
- [x] Wrap `face_service.get_embedding()` calls with `run_in_threadpool` in endpoints to unblock the async event loop.
- [x] Implement robust error handling for edge cases in `face_service.py`.

## Phase 3: Service Layer Extraction
- [x] Extract heavy analytics and Pandas logic from endpoints into `services/analytics_service.py`.
- [x] Extract Supabase queries into a dedicated database repository layer (`services/db_service.py`).

## Phase 4: Frontend UI/UX Refinement
- [x] Move inline styles in `register.html` to proper Tailwind classes.
- [x] Standardize the color palette and typography across all HTML templates.
- [x] Extract inline JavaScript from HTML files into dedicated `.js` files inside `static/js/`.
- [x] Migrate Geofencing validation logic from client-side JS to backend API.

## Phase 5: Verification
- [x] Test the entire face registration and attendance flow.
- [x] Test Dashboard analytics and Excel export functionality.
- [x] Review code against the "Demand Elegance" standard before marking as complete.
