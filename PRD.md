# 📄 Product Requirements Document (PRD)
**Project Name:** FaceID-KP (KP Bromo Hub)
**Current Version:** 2.0 (Transitioning)

## 1. Product Overview
**FaceID-KP** is evolving from a facial-recognition attendance kiosk into the central digital community portal for Komisi Pemuda (KP) GKI Bromo Malang. The application serves two main audiences:
1. **Jemaat (Youth Members):** To explore community events, learn about the KP's vision, and track their personal spiritual/attendance growth.
2. **Pengurus (Committee):** To track attendance, identify unengaged/at-risk youths, and streamline event management using AI and data.

## 2. Core Principles (The "Zero-Bullshit" Philosophy)
- **Modularity:** Frontend and Backend must remain loosely coupled. FastAPI for logic, plain HTML/Tailwind for presentation.
- **Performance First:** The ML inference and database queries must not block the async event loop.
- **Privacy & Security:** Row Level Security (RLS) is strictly enforced in Supabase. Face embeddings are securely handled.
- **Elegance:** The UI must feel premium, responsive, and deeply engaging (glassmorphism, micro-animations, consistent hierarchy).

## 3. Key Features
### Phase 1 (Completed)
- [x] High-speed Facial Recognition via Cosine Similarity.
- [x] Supabase integration for Users, Logs, and Embeddings.
- [x] Admin Dashboard (Heatmap, Peak Time, Demographics).
- [x] JWT Authentication & Geofencing security.

### Phase 2 (In Progress - KP Hub Pivot)
- [ ] **Public Landing Page (`/`):** Display vision, mission, team, and monthly curriculum.
- [ ] **Event Calendar:** A dynamic display of upcoming fellowships and retreats.
- [ ] **Dedicated Kiosk Route (`/kiosk`):** The FaceID scanner isolated to its own secure route.
- [ ] **User Portal:** A place for jemaat to log in and view their data/RSVP.

## 4. Technical Architecture
- **Backend:** Python (FastAPI).
- **Database:** Supabase (PostgreSQL with `pgvector` for embeddings).
- **AI/ML:** MediaPipe (Face Detection/Landmarks).
- **Frontend:** Vanilla JS, HTML, Tailwind CSS (No Frameworks).
- **Data Transport:** JSON REST API.

## 5. Future Roadmap Sync
This document must be updated in tandem with `tasks/komisi_pemuda_roadmap.md` whenever core business logic or architectural shifts occur. Never stray from the core principles listed here without explicit user permission.
