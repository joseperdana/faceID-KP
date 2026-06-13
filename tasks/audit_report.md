# Architectural Audit Report: KPBromoMalang (FaceID-KP)

## 1. Backend & ML Pipeline (FastAPI)
- **Monolithic Routing:** All routes (HTML pages, APIs, Analytics, Admin) are currently defined in `main.py` (over 600 lines). This violates the modular routing requirement. 
- **Pydantic Validation Deficiencies:** While simple models like `LoginDto` exist, critical endpoints like `/api/register` and `/api/recognize` use raw `Form` or `UploadFile` without comprehensive structured schemas. Response models are not utilized, resulting in raw dictionaries being returned.
- **Event Loop Blocking:** The `face_service.get_embedding(content)` method performs heavy CPU-bound model inference (InsightFace). Currently, it is called synchronously inside `async def` endpoints (`/api/recognize` and `/api/register`). This blocks the FastAPI async event loop, causing the server to hang for other requests while processing an image.

## 2. Security & Supabase
- **Authentication Flaw (Static Token):** The `check_admin_auth` dependency uses a hardcoded, static session token (`"rahasia_negara"`). This is a severe security vulnerability. It should use a proper cryptographic JWT or a secure session management system.
- **Supabase Integration & RLS:** The database client is initialized globally in `database.py`. However, there's no dynamic context passing for Row Level Security (RLS). The server currently acts as a privileged client. If the backend uses the `service_role` key, RLS is completely bypassed.
- **Frontend Security (Geofencing):** The frontend implements geofencing, but relies solely on client-side validation. A malicious user could easily bypass this by spoofing the GPS coordinates or modifying the JS logic.

## 3. Frontend Architecture (Tailwind & HTML)
- **Inline Styles & Redundancy:** Despite using Tailwind CSS, there are instances of inline CSS (e.g., `style="margin-top: 15px; ..."` in `register.html`). This breaks consistency.
- **Component Reusability:** As a framework-less HTML project, UI elements like buttons, navbars, and modals are duplicated across pages. We should use Tailwind's `@layer components` or a standardized class-naming convention to maintain consistency.
- **UX Flow:** The user feedback during face scanning is good, but the JavaScript logic is tightly coupled with the HTML structure, making it harder to scale or maintain.

## 4. Code Quality & Architecture ("Demand Elegance")
- **Spaghetti Code in Analytics:** The `/api/analytics` and `/api/export-excel` endpoints contain massive blocks of data processing logic (calculating heatmaps, missing days, pandas DataFrame generation). This logic should be extracted into dedicated service layers (e.g., `services/analytics_service.py`).
- **Temporary Fixes:** The explicit string casts and error-swallowing `try-except: pass` blocks in the analytics code are temporary fixes that hide underlying data type issues.
- **Error Handling:** Sentry is initialized, but custom HTTPException handling is basic. Unhandled exceptions in the ML pipeline or DB layer return generic 500s without clear, structured error responses for the client.
