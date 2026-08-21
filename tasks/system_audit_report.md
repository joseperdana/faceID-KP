# 🔍 FaceID-KP — System Audit Report
**Auditor Role:** Senior Systems Architect & Principal UI/UX Designer  
**Scope:** Full codebase audit — Backend, ML Pipeline, Security, Dashboard UX  
**Date:** July 6, 2026  
**Verdict:** System is functional and architecturally more mature than average hobby projects. However, it has three production-blocking vulnerabilities and three UX flaws that will actively confuse your admin user under real-world load.

---

## PART 1: CRITICAL BACKEND VULNERABILITIES

---

### 🔴 Vulnerability #1 — Race Condition on Duplicate-Check/Write (TOCTOU Bug)

**Severity:** Critical | **Probability of Production Failure:** High

**Root Cause in Code:**  
[`routers/kiosk.py` L63–L92](file:///Users/josetaneo/Private_Coding/faceID-KP/routers/kiosk.py#L63-L92)

```python
# Line 63–66: CHECK if user attended today
history = DBService.get_user_history(user_id)
check_log = [log for log in history if log['timestamp'] >= today_start]

# Line 75–92: If no log found → INSERT
if len(check_log) > 0:
    return { "status": "success", "message": "sudah absen hari ini!" }

DBService.insert_log(log_data)  # <-- WRITE happens here
```

**The Exact Failure Mode:**  
This is a classic TOCTOU (Time-Of-Check-Time-Of-Use) race condition. If two requests for the same `user_id` hit the server within milliseconds of each other — which is entirely realistic if someone scans twice quickly or if network latency causes a retry — both will pass the `check_log` guard simultaneously and both will execute `insert_log`. The result is **a duplicate attendance entry for the same person on the same day** with no database-level protection to stop it.

Your `get_user_history` call also fetches **the entire attendance history of a user** to then filter it in Python (Line 63–66). For a user with 2 years of logs, this is a full table scan on their records on every single recognition attempt. At a church event with 50 people in 30 minutes, that is 50 full scans.

**The Database Has No Unique Constraint.**  
There is no `UNIQUE` constraint on `(user_id, DATE(timestamp))` in the `attendance_logs` table. The only guard is application-level Python code running asynchronously. This will produce duplicate data.

---

### 🔴 Vulnerability #2 — Synchronous DB Calls Are Blocking the Async FastAPI Event Loop

**Severity:** Critical | **Probability of Production Failure:** High

**Root Cause in Code:**  
[`services/db_service.py`](file:///Users/josetaneo/Private_Coding/faceID-KP/services/db_service.py) — all 15+ methods  
[`routers/kiosk.py` L52, L63, L84, L92](file:///Users/josetaneo/Private_Coding/faceID-KP/routers/kiosk.py#L52-L92)

```python
# kiosk.py — the recognize endpoint does this sequence SYNCHRONOUSLY:
matches = DBService.match_faces(query_vector)   # Line 52 — blocking I/O
history = DBService.get_user_history(user_id)   # Line 63 — blocking I/O
DBService.insert_log(log_data)                  # Line 92 — blocking I/O
```

The `FaceService.get_embedding()` call is correctly offloaded to a thread pool via `run_in_threadpool` (Line 43). This is good. But every single database call after it is a **raw synchronous `supabase-py` HTTP call** made directly on the async event loop thread.

The `supabase-py` client is a **synchronous library**. Every `.execute()` call blocks the event loop. During a recognition cycle, three blocking DB calls fire in sequence — `match_faces` (a pgvector RPC), `get_user_history`, and `insert_log`. While these are waiting on network I/O to Supabase, FastAPI cannot process any other incoming request. Under a peak of 10 simultaneous users scanning, you have up to 30 blocked DB calls queued, and your server's apparent throughput collapses.

The same problem exists in `analytics_service.py` where `calculate_dashboard_stats()` fires **4 sequential synchronous DB calls** (Lines 10–13) every time the dashboard loads.

> [!CAUTION]
> This is not theoretical. You will see this manifest as slow recognition responses and timeout errors during any event where more than 5 people scan within the same minute.

---

### 🔴 Vulnerability #3 — Hardcoded Fallback Secret Key + No Rate Limiting on Auth or Kiosk

**Severity:** Critical | **Probability of Production Failure:** Medium (but catastrophic if triggered)

**Root Cause in Code:**  
[`core/security.py` L7](file:///Users/josetaneo/Private_Coding/faceID-KP/core/security.py#L7)

```python
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key_change_me")
```

If the `SECRET_KEY` environment variable is missing from `.env` — which happens during a fresh deployment, Docker container restart, or misconfigured environment — the application silently falls back to a publicly known, hardcoded key. Any attacker who reads your open-source repo can forge a valid admin JWT token and gain full dashboard access.

**Compounding Problem — No Rate Limiting Anywhere:**  
[`routers/auth.py`](file:///Users/josetaneo/Private_Coding/faceID-KP/routers/auth.py) and [`routers/kiosk.py`](file:///Users/josetaneo/Private_Coding/faceID-KP/routers/kiosk.py) have zero rate limiting. The `/api/login` endpoint can be brute-forced indefinitely. The `/api/recognize` endpoint can be hammered with spoofed images or used to enumerate known face embeddings. Geofencing (`lat/lng`) is easily bypassed since the parameters are optional — if `lat` and `lng` are simply omitted from the request, the geofence check is entirely skipped (Lines 34–37).

```python
# kiosk.py Line 34 — The geofence is 100% optional. Send no lat/lng = bypass.
if lat is not None and lng is not None:
    distance = calculate_distance(...)
```

**Also: The Sentry DSN is hardcoded in `main.py`**  
[`main.py` L10](file:///Users/josetaneo/Private_Coding/faceID-KP/main.py#L10) — The DSN is committed to source code. This lets anyone send arbitrary error events to your Sentry project, exhausting your quota.

---

## PART 2: CRITICAL UI/UX FLAWS

---

### 🟠 UX Flaw #1 — The Analytics Tab is Metric Bloat That Buries the One Critical Alert

**Severity:** High | **Impact:** Admin misses at-risk members

**Root Cause in UI:**  
[`dashboard.html` L182–L315](file:///Users/josetaneo/Private_Coding/faceID-KP/frontend/dashboard.html#L182-L315)

The Analytics tab renders 7 distinct data widgets in a single scroll view:
1. Average Attendance KPI card
2. Peak Time bar chart
3. Attendance Trend line chart
4. Gender Distribution bar
5. Calendar Heatmap (full horizontal scroll widget)
6. **"At-Risk" member list** ← The one thing that requires a pastoral action
7. "Most Diligent" leaderboard

The **At-Risk panel** (jemaat who haven't shown up in 30+ days with their phone numbers) is the **only widget on this entire dashboard that drives a real-world action** (a phone call or pastoral visit). It is buried at position 6 of 7, below a heatmap that requires horizontal scrolling. An admin using this dashboard weekly will visually skim past it.

The "Jemaat Paling Rajin" (Most Diligent Leaderboard) is displayed at equal visual weight alongside the At-Risk panel. A leaderboard is an engagement metric, not an administrative action item. Its presence at the same hierarchy level dilutes the urgency of the At-Risk panel.

> [!WARNING]
> **Cognitive Load Principle Violated:** Miller's Law. Seven information clusters in one view is three too many. The admin's eye has no clear primary focal point.

---

### 🟠 UX Flaw #2 — The "Live" Activity Feed is Neither Live Nor Useful

**Severity:** Medium | **Impact:** False sense of real-time monitoring; data staleness is invisible

**Root Cause in UI:**  
[`dashboard.html` L97, L601–L637](file:///Users/josetaneo/Private_Coding/faceID-KP/frontend/dashboard.html#L97-L637)

The overview panel displays a `● Live` badge (green, animated pulse) next to "Aktivitas Terbaru". This is misleading. The feed is populated once on tab load (`loadOverview()` is called on tab switch) and **never auto-refreshes**. There is no `setInterval`, no WebSocket, no SSE. The data goes stale the moment the page loads.

The feed also only shows **5 most recent logs** (the `get_recent_logs(limit=5)` call in `analytics_service.py` Line 13). During a church event where 40 people scan within one hour, the feed shows only the last 5 and the admin has no way to know anyone else checked in without manually clicking "Lihat Semua Riwayat".

The `● Live` label actively creates a false expectation of real-time data. When an admin sees someone scan at the kiosk and the feed doesn't update, they will interpret it as a system failure, not a design limitation.

---

### 🟠 UX Flaw #3 — User Delete Has No Confirmation Guard; XSS Vector in innerHTML Injection

**Severity:** High | **Impact:** Irreversible data loss + potential XSS injection

**Root Cause in UI:**  
[`dashboard.html` L624–L634](file:///Users/josetaneo/Private_Coding/faceID-KP/frontend/dashboard.html#L624-L634)

```javascript
// dashboard.html — innerHTML injection with server data, no sanitization
tbody.innerHTML += `
    <td class="p-4 font-semibold text-slate-700">${name}</td>
    <td class="p-4"><span class="${statusClass}...">${log.status}</span></td>
`;
```

Every data field rendered into the table (`name`, `log.status`, `time`) is injected directly via `innerHTML` string concatenation. If a user's `full_name` in the database contains `<img src=x onerror=alert(1)>`, that script executes in the admin's browser. This is a stored XSS vulnerability. Since you control registration, this is low probability in a closed community — but it only takes one malicious registration to compromise the admin session.

**Separate Issue — Delete User Has No Soft-Delete or Undo:**  
[`routers/users.py` L50–L57](file:///Users/josetaneo/Private_Coding/faceID-KP/routers/users.py#L50-L57)

```python
@router.delete("/{user_id}")
async def delete_user(user_id: int):
    DBService.delete_logs_by_user(user_id)  # All attendance history gone
    DBService.delete_user(user_id)           # User gone
```

Delete is a two-step hard cascade with no soft-delete flag, no archive, and no confirmation beyond a SweetAlert dialog on the frontend. If the admin accidentally clicks delete on the wrong person, all their attendance history is permanently destroyed. There is no recovery path.

---

## PART 3: STEP-BY-STEP MITIGATIONS

---

### Fix #1 — Eliminate the Race Condition (TOCTOU)

**Step 1:** Add a database-level unique constraint. Run this in Supabase SQL Editor:

```sql
-- Enforce one attendance record per user per calendar day (UTC)
ALTER TABLE attendance_logs
ADD CONSTRAINT unique_user_per_day 
UNIQUE (user_id, (DATE(timestamp AT TIME ZONE 'UTC')));
```

**Step 2:** Remove the Python-level duplicate check in `kiosk.py`. Replace the entire history-fetch-and-filter block with a targeted, indexed query:

```python
# Replace Lines 62-85 in kiosk.py with this atomic approach
today_iso = datetime.now(timezone.utc).date().isoformat()
today_log = DBService.check_user_log_today(user_id, today_iso)  # targeted query
if today_log:
    return {"status": "already_attended", ...}
# If the DB constraint fires on insert, catch the exception → return already_attended
```

**Step 3:** Wrap `insert_log` in a try/except that catches the unique constraint violation from Supabase (it will return a `PostgrestAPIError` with code `23505`).

---

### Fix #2 — Stop Blocking the Event Loop

**Option A (Recommended for your scale):** Wrap all synchronous `DBService` calls in `run_in_threadpool`:

```python
# In kiosk.py, wrap every DB call
from starlette.concurrency import run_in_threadpool

matches = await run_in_threadpool(DBService.match_faces, query_vector)
today_log = await run_in_threadpool(DBService.check_user_log_today, user_id, today_iso)
await run_in_threadpool(DBService.insert_log, log_data)
```

**Option B (Better long-term):** Switch to `supabase-py`'s async client:

```python
# database.py
from supabase import acreate_client, AsyncClient
supabase: AsyncClient = await acreate_client(url, key)
```

Then all `DBService` methods become `async def` and use `await`.

**For `analytics_service.py`:** Cache the `dashboard_stats` response for 30 seconds using FastAPI's `cachetools` or a simple in-memory TTL dict. The dashboard does not need live-second accuracy.

---

### Fix #3 — Harden Security

**Secret Key — fail loudly, not silently:**
```python
# core/security.py — Remove the fallback entirely
SECRET_KEY = os.environ["SECRET_KEY"]  # Raises KeyError on startup if missing
```

**Rate Limiting — add `slowapi`:**
```python
# main.py
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# auth.py
@limiter.limit("5/minute")
@router.post("/login")
def api_login(...): ...

# kiosk.py
@limiter.limit("30/minute")
@router.post("/recognize")
async def recognize_face(...): ...
```

**Geofence — make location mandatory for the kiosk endpoint:**
```python
# kiosk.py — enforce lat/lng at Pydantic level, not as Optional
lat: float = Form(...),  # Remove Optional
lng: float = Form(...),  # Remove Optional
```

**Move Sentry DSN to environment variable:**
```python
# main.py
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"), ...)
```

---

### Fix #4 — Restructure the Analytics Tab (UX)

**Principle:** One primary action per screen. The admin's job is pastoral: identify and contact at-risk members.

**Proposed Layout Change:**

```
[Analytics Tab]
│
├── ROW 1: KPI Cards (avg attendance, peak time) — compressed, 2 cols
│
├── ROW 2 [PINNED/HIGHLIGHTED]: ⚠️ At-Risk Members — RED BORDER, full width,
│         TOP of page, not buried at bottom. This is the call-to-action.
│
├── ROW 3: Trend Chart (collapsible, default collapsed on mobile)
│
└── ROW 4: [Accordion] → Gender | Heatmap | Leaderboard (secondary data)
```

Remove the leaderboard from primary view. Move it into the "Database Jemaat" tab as a sort option — it belongs with member management, not with analytics.

---

### Fix #5 — Make the Feed Actually Live + Remove False "● Live" Badge

**Step 1:** Replace the fake Live badge with a "Last Updated" timestamp.

**Step 2:** Add auto-refresh with a 30-second interval:
```javascript
// In the Overview tab init
let overviewInterval = null;

function startOverviewRefresh() {
    loadOverview();
    overviewInterval = setInterval(loadOverview, 30000); // every 30s
}
function stopOverviewRefresh() {
    clearInterval(overviewInterval);
}
// Call startOverviewRefresh() on tab switch to 'overview'
// Call stopOverviewRefresh() on tab switch away
```

**Step 3:** Increase `get_recent_logs(limit=5)` to `limit=15` for event days, or make the limit a config param.

---

### Fix #6 — Sanitize innerHTML + Add Soft Delete

**XSS Fix — use `textContent` instead of `innerHTML` for user data:**
```javascript
// Replace innerHTML string concatenation with DOM API
const td = document.createElement('td');
td.className = 'p-4 font-semibold text-slate-700';
td.textContent = name;  // safe — no HTML execution
row.appendChild(td);
```

**Soft Delete — add `is_deleted` flag:**
```sql
ALTER TABLE users ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;
```

```python
# services/db_service.py — soft delete
@staticmethod
def soft_delete_user(user_id: int):
    supabase.table("users").update({
        "is_deleted": True,
        "deleted_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", user_id).execute()
```

This preserves attendance history and allows recovery within a grace period.

---

## Summary Table

| # | Finding | Severity | Effort to Fix | Risk if Ignored |
|---|---------|----------|---------------|-----------------|
| B1 | TOCTOU Race Condition → Duplicate Logs | 🔴 Critical | Low (1 SQL line + 10 LOC) | Data integrity corruption |
| B2 | Sync DB Calls Blocking Async Loop | 🔴 Critical | Medium (refactor all DB calls) | Server timeout under load |
| B3 | Hardcoded Fallback Key + No Rate Limit | 🔴 Critical | Low-Medium | Admin session hijack / brute force |
| U1 | At-Risk Panel Buried in Metric Bloat | 🟠 High | Medium (layout restructure) | Pastoral misses go unnoticed |
| U2 | Fake "● Live" Feed + Staleness | 🟠 Medium | Low (setInterval + label fix) | Admin distrust of system |
| U3 | innerHTML XSS + Hard Cascade Delete | 🟠 High | Low (DOM API + soft delete migration) | Data loss / session compromise |

> [!IMPORTANT]
> **Recommended Fix Order:** B3 (security, lowest effort) → B1 (data integrity) → U3 (XSS + delete) → B2 (performance) → U1 + U2 (UX polish)

---

## Key Architectural Observation

The system's pivot from a standalone kiosk to a full community portal (Phase 2) makes **Fix B2 non-negotiable**. A public-facing landing page + event calendar + user portal running on the same FastAPI process as the ML inference engine — with synchronous DB calls — will collapse under any meaningful traffic. Before Phase 2 ships, the DB layer must be async-capable.
