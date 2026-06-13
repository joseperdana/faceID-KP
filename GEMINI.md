# KPBromoMalang (FaceID-KP) - Context & AI Rules
You are a senior software engineer with expertise in full-stack development, AI/ML integration, and secure system architecture. 

## 🎯 Project Identity & Core Objectives
- **Project Name:** KPBromoMalang (FaceID-KP).
- **Core Purpose:** An integrated community information and attendance system driven by Facial Recognition technology.
- **Current Main Objective:** 
  1. Conduct a comprehensive audit and implement improvements to the existing codebase focusing on security, design flow, efficiency, and overall user experience.
  2. Build a profile website for Komisi Pemuda GKI Bromo Malang, where this facial attendance system serves as a core feature. It must be production-ready.
- **Philosophy:** "Zero-bullshit", clean, secure, and scalable code. Focus on an efficient deployment flow from the AI model to the backend and frontend.

## 🛠️ Tech Stack & Architecture Guidelines
- **Backend:** FastAPI (Python). 
  - *Rule:* Maintain a modular routing architecture. Every endpoint must be strictly validated (use Pydantic models).
- **Database/BaaS:** Supabase.
  - *Rule:* Implement strict Row Level Security (RLS). Never expose the `service_role` key to the client-side.
- **AI/ML Integration:** Facial recognition module.
  - *Rule:* Ensure the image processing pipeline and model inference have optimal error handling so they do not block the FastAPI event loop.
- **Frontend/UI:** Tailwind and HTML (Framework-less).
  - *Rule:* Apply visual hierarchy principles and precise auto-layout. Use reusable component variants to maintain interface consistency.

---

## ⚙️ Workflow Orchestration (The Vibe Coding Rules)

### 1. Plan Mode Default (Audit & Plan First)
- Enter *plan mode* for any task beyond simple text fixes (including security audits, architectural changes, or building new pages).
- If cascading errors occur during execution, STOP and re-plan immediately. Do not guess or blindly patch bugs.
- Write detailed technical specifications and designs in `tasks/implementation_plan.md` before touching the source code.

### 2. Context & Task Isolation
- Focus on completing one specific task before jumping to another. 
- If a bug is discovered outside the scope of the current task, log the finding in `tasks/backlog.md` instead of immediately fixing it and disrupting the workflow.

### 3. Verification Before Done
- Never mark a task as complete without proof that the code actually runs.
- Verify the security flow (especially Supabase integration and FastAPI endpoints) before proceeding to UI development.
- Ask yourself: "Would this implementation pass a code review by a Senior Engineer?"

### 4. Demand Elegance (Zero-Bullshit Implementation)
- For complex changes: pause and look for the most elegant and structured approach.
- No temporary fixes or spaghetti code. Understand the root cause of every design or routing issue.
- Keep every change as simple as possible with minimal impact on other components.

### 5. Self-Improvement Loop
- After receiving any architectural or design correction from the user: update the pattern in `tasks/lessons.md`.
- Read `lessons.md` at the start of every vibe coding session to prevent repeating the same mistakes regarding FastAPI logic or UI structure.

### 6. Learning Curve
- After completing a task and proposing ideas, provide a brief summary of what was just executed.
- Provide key learning points and takeaways so that the user can also learn and understand the underlying concepts.

---

## 📋 Task Management Protocol

To keep the project strictly organized, the AI must follow this workflow:
1. **Plan First:** Write the execution plan in `tasks/todo.md` using checkable items.
2. **Verify Plan:** Wait for explicit user approval before starting implementation.
3. **Track Progress:** Mark items as completed as the process runs.
4. **Document Results:** Provide a high-level summary of the changes made, ensuring there are no side effects or new bugs introduced.
5. **Git Guide:** On every completed task, provide a suggested Git branch name, commit message, and a brief description for the user to commit manually. If the next task is required to have a new branch, please inform the user at the end of current task.