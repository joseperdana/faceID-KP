# 🚀 FaceID-KP to KP Bromo Hub: Strategic Roadmap

## 🎯 The Vision
Transforming an internal attendance tracking tool into the central digital heartbeat of **Komisi Pemuda (KP) GKI Bromo Malang**. This plan transitions the software from a simple "FaceID Kiosk" into a comprehensive, gamified, and AI-driven Community Hub that fosters engagement, spiritual growth, and operational excellence.

---

## 🟢 Version 1.0: The Solid Foundation (Current Phase)
*The core FaceID and Attendance Engine. Reliable, fast, and secure.*

### Focus Areas
- **Facial Recognition Engine:** Fast inference (< 100ms) with high accuracy using MediaPipe and Cosine Similarity.
- **Admin Command Center:** Powerful, data-rich dashboard for the pengurus (committee) to track trends, peak times, and gender distributions.
- **Geofencing & Anti-Spoofing:** Ensuring check-ins only happen precisely at the GKI Bromo Malang coordinates.
- **UX Polish:** Premium glassmorphism UI and seamless feedback loops for the jemaat during scanning.

**Status:** `Completed & Ready for Field Testing.`

---

## 🟡 Version 2.0: The Community Pivot (The Nearest Plan)
*Transitioning from a purely functional kiosk tool to a public-facing Community Portal.*

### Focus Areas
- **UUI/UX Improvements**
  - **UI Design Creation:** Create a DESIGN.md file to produce new design system for the whole app with stitch.
  - **UI Design Implementation:** Implement the new design system for the whole app.
  - **UX Evaluation:** Run a complete diagnostic of User Experience for whole app.
- **Public Profile Website (`/`):** 
  - **About KP:** Vision, Mission, and Core Values.
  - **The Team:** Interactive cards showing the Pengurus (Committee) structure.
  - **Curriculum & Themes:** Displaying the monthly spiritual themes and upcoming sermon topics.
- **Event Management System:**
  - Dynamic calendar of upcoming fellowships (Persekutuan Sabtu), retreats, and sports events.
- **Jemaat Personal Portal:**
  - Users can log in using their Face (via webcam at home) or Phone Number/OTP.
  - They can view their own attendance streaks, update their profile, and RSVP for special events.
- **Kiosk Isolation:** 
  - The current FaceID scanner is moved to a dedicated, locked route (e.g., `/kiosk`) designed exclusively to run full-screen on an iPad/Tablet mounted at the church entrance.

---

## 🟠 Version 3.0: Engagement & Gamification
*Leveraging data to increase participation and build stronger relationships.*

### Focus Areas
- **Automated WhatsApp Integration (BaaS):**
  - **Pre-Event:** Automated Friday reminders ("See you tomorrow at KP!").
  - **Retention:** Triggered "We missed you!" messages for youths who haven't attended in 3+ weeks (The "At-Risk" demographic).
  - **Celebration:** Automated Happy Birthday wishes with personalized graphics.
- **Gamification & Badges:**
  - Jemaat earn digital badges/achievements for consistency (e.g., "On Fire: 4x consecutive attendance", "Early Bird: Arrived 15 mins before start").
  - A friendly, opt-in leaderboard to foster community excitement.
- **Digital Offering/Donation (Persembahan):**
  - QRIS integration directly on the portal for seamless digital offerings.

---

## 🔴 Version 4.0: Advanced AI & "Smart Ministry"
*Pushing the boundaries of what a church community application can do using cutting-edge AI.*

### Focus Areas
- **Emotion & Vibe Analysis (Opt-In):**
  - While scanning faces at the kiosk, the ML model passively detects aggregate mood/expressions (e.g., smiling, neutral). The dashboard provides a "Congregation Vibe Index" to help the worship team understand engagement.
- **Predictive Analytics:**
  - Correlating attendance data with external factors. The system warns the committee: *"Historically, attendance drops 20% during UB/UM University Midterm weeks. Suggest planning an exam-relief chill event."*
- **Multi-Device Synchronization:**
  - Scaling up to 3-4 simultaneous FaceID kiosks at the entrance, utilizing WebSockets (FastAPI + Redis) for instant synchronization and zero bottlenecks during rush hour.
- **AI Chatbot (Spiritual Companion):**
  - An embedded RAG (Retrieval-Augmented Generation) chatbot trained on past sermons, KP curriculums, and biblical principles to answer questions or provide prayer prompts for the youth 24/7.

---

## 🛠️ Execution Strategy for V2.0 (Next Steps)
If we proceed with **Version 2.0**, our immediate technical plan will be:
1. **App Profile:** Create a complete Product Requirements Document (PRD) for the app and update it if needed in the future.
2. **Design Creation:** Create a DESIGN.md file.
3. **Architecture Shift:** Re-route the `index.html` to serve the new Public Landing Page. 
4. **Component Library:** Build reusable Tailwind components for Events, Team Members, and Curriculum timelines.
5. **Database Expansion:** Add new Supabase tables: `events`, `curriculum`, `team_roles`.
6. **Kiosk Route:** Migrate the current FaceID camera logic strictly to `/kiosk`.

*Built with Zero-Bullshit Philosophy. Scalable, Secure, Elegant.*
