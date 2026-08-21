# 🧠 Project Wiki & Brain: FaceID-KP

> **DevBrain Hub**: `dev_brain/` ➔ `~/DevBrain/01_Projects/FaceID-KP/`  
> **Global Knowledge Vault**: `global_brain/` ➔ `~/DevBrain/`

---

## 🗺️ Wiki Links & Knowledge Graph Nodes
- **Domain MOC**: [[_MOC_Backend_and_Cloud]] & [[_MOC_AI_and_Computer_Vision]]
- **Atomic Concepts**:
  - [[Vector_Search_and_pgvector]] — 512-d embeddings & cosine distance.
  - [[Async_Event_Loops]] — Non-blocking FastAPI event loop.
  - [[FastAPI_Framework]] — Routing, Pydantic validation & SlowAPI.
- **Architectural Decision Records (ADRs)**:
  - [[ADR-001-pgvector-vs-external-saas]] — Why PostgreSQL pgvector won over Pinecone.
  - [[ADR-002-fastapi-worker-thread-pools]] — Isolating ONNXRuntime inference to worker threads.
  - [[ADR-003-client-side-canvas-photobooth]] — Zero-latency client-side HTML5 canvas photobooth rendering for KP45 event.
  - [[ADR-004-kiosk-fast-manual-fallback]] — Non-blocking manual autocomplete fallback with `method` audit trail.
- **Post-Mortems**:
  - [[2025-FastAPI-Worker-Thread-Starvation]] — Root cause & fix for attendance queue latency spikes.

---

## 🤖 Instructions for AI Coding Assistants (Antigravity / Cursor)
When developing or refactoring this repository:
1. Consult `dev_brain/` and `PRD.md` for PRD, database schema specs, and architecture rules before modifying endpoints.
2. Ensure CPU-bound ML inference and synchronous DB I/O are offloaded via `run_in_threadpool` to prevent thread starvation.
3. If an architectural decision or major bug is resolved, log it into `global_brain/04_ADRs/` or `global_brain/06_Postmortems/`.
