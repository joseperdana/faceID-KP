# 🛡️ FaceID-KP: Smart Attendance System
> A high-performance, web-based facial recognition attendance system for youth organizations.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

## 📖 Overview
**FaceID-KP** was developed to modernize attendance tracking for large youth groups (70-130 members). By replacing manual logs with a seamless facial recognition kiosk, the system ensures data accuracy, prevents proxy attendance, and speeds up the check-in process during events.

---

## ✨ Key Features
* **🤖 AI-Powered Recognition:** Leverages **InsightFace (ArcFace)** for high-accuracy identity verification.
* **⚡ Vector Search:** Integrated with **Supabase (PostgreSQL + pgvector)** for lightning-fast similarity searches across the member database.
* **📍 GPS Geofencing:** Prevents "remote check-ins" by ensuring the user is physically present at the venue coordinates.
* **🖥️ Kiosk Mode:** An automated "Auto-Scan" interface with stability checks to prevent accidental or duplicate triggers.
* **🔒 Secure Enrollment:** A dedicated workflow for registering member faces with quality validation.

---

## 🛠️ Tech Stack
* **Backend:** FastAPI (Python)
* **Database:** Supabase
* **AI Models:** InsightFace
* **Deployment:** VPS (Ubuntu 24.04)
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
