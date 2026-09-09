# 🛡️ FaceID-KP: Smart Attendance System
> A high-performance, web-based facial recognition attendance system for youth organizations.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> **Upgrading from v2.0?** Read [`UPGRADE.md`](UPGRADE.md) first — this release
> adds required configuration, a database migration, and a one-time kiosk device
> enrolment step.

## 📖 Overview
**FaceID-KP** was developed to modernize attendance tracking for large youth groups (70-130 members). By replacing manual logs with a seamless facial recognition kiosk, the system ensures data accuracy, prevents proxy attendance, and speeds up the check-in process during events.

---

## ✨ Key Features
* **🤖 AI-Powered Recognition:** Leverages **InsightFace (ArcFace)** for high-accuracy identity verification.
* **⚡ Vector Search:** Integrated with **Supabase (PostgreSQL + pgvector)** for lightning-fast similarity searches across the member database.
* **📍 GPS Geofencing:** Reduces accidental check-ins from home. The browser supplies the coordinates and the server cannot verify them, so this is a convenience control, not proof of presence — see PRD §9.
* **🖥️ Kiosk Mode:** An automated "Auto-Scan" interface with stability checks to prevent accidental or duplicate triggers.
* **🔒 Secure Enrollment:** Registration requires an enrolled kiosk device or an admin session, and explicit biometric consent (UU 27/2022).
* **↩️ Manual Fallback:** Name search that keeps attendance running when the camera, the model, or the network is unavailable.

---

## 🛠️ Tech Stack
* **Backend:** FastAPI (Python)
* **Database:** Supabase
* **AI Models:** InsightFace
* **Deployment:** VPS (Ubuntu 24.04), `scripts/deploy_vps.sh`
* **Frontend:** HTML/Tailwind

---

## 🚀 Getting Started

### Prerequisites
* Python 3.9+
* Supabase Account (with pgvector extension enabled)

### Installation
1. **Clone the repository:**
   ```bash
   git clone [https://github.com/joseperdana/faceID-KP.git](https://github.com/joseperdana/faceID-KP.git)
   cd faceID-KP
   ```

2. **Install dependencies:**
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements-dev.txt
   ```

3. **Configure:**
   ```bash
   cp .env.example .env
   python scripts/generate_secrets.py   # SECRET_KEY, KIOSK_TOKEN
   python scripts/hash_password.py      # ADMIN_PASSWORD_HASH
   ```
   Fill in the Supabase values and the church coordinates. Verify the
   coordinates on a map — there is deliberately no default, because the
   repository previously carried two that were ~965 m apart.

4. **Apply the schema:**
   ```bash
   psql "$SUPABASE_DB_URL" -f migrations/001_init.sql
   ```

5. **Run:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. **Enrol the kiosk device** — sign in at `/login`, then open `/kiosk/enroll`
   on the tablet. Once per device.

### Tests

```bash
pytest tests/ --ignore=tests/test_e2e_playwright.py   # unit + integration
ruff check . && ruff format --check .                 # lint
node scripts/check_theme_tokens.js                    # undefined Tailwind tokens
```

## 📋 Project documents

| File | Purpose |
| :--- | :--- |
| [`PRD.md`](PRD.md) | Requirements, thresholds, NFR budget, open questions |
| [`UPGRADE.md`](UPGRADE.md) | Migration steps for this release |
| [`tasks/AUDIT_2026-09-08.md`](tasks/AUDIT_2026-09-08.md) | Full audit findings |
| [`migrations/001_init.sql`](migrations/001_init.sql) | Canonical database schema |
| [`.env.example`](.env.example) | Every configuration value, annotated |

## 📄 License

MIT
