# Upgrade to v2.1 (post-audit)

This release changes configuration, the database schema and several API response
shapes. Read this before deploying — the application will refuse to start if the
new required variables are missing, which is deliberate: a half-configured server
that boots is worse than one that tells you what is wrong.

Full findings: `tasks/AUDIT_2026-09-08.md`.

---

## 0. Before anything else — rotate the leaked credentials

`.env` was committed in `c3b7558d` and is still readable in git history. Removing
a file from the working tree does not remove it from history.

```bash
git show c3b7558d:.env      # confirm for yourself what leaked
```

Four values are exposed: `SUPABASE_URL`, `SUPABASE_KEY`, `ADMIN_PASSWORD`,
`SECRET_KEY`. The last of these signs admin sessions, so anyone holding it can
mint a valid admin token without ever visiting the login page — rate limiting is
irrelevant to that attack.

1. **Make the repository private.** It stops the bleeding; it does not recall
   clones or forks that already exist.
2. **Rotate all four:**
   ```bash
   python scripts/generate_secrets.py   # SECRET_KEY + KIOSK_TOKEN
   python scripts/hash_password.py      # ADMIN_PASSWORD_HASH
   ```
   Rotate the Supabase API key in the Supabase dashboard.
3. **Purge history** once the rotation is done:
   ```bash
   git filter-repo --invert-paths --path .env --path venv --path static/images
   git push --force --all && git push --force --tags
   ```
   Then ask GitHub Support to expire cached views of the old commits.
4. **Two face photos** of identifiable people were committed under
   `static/images/`. They are removed from the tree here and from history by the
   step above. Tell the two people concerned.

---

## 1. Apply the database migration

The schema was never in version control. `migrations/001_init.sql` is idempotent
and safe against an existing database.

```bash
psql "$SUPABASE_DB_URL" -f migrations/001_init.sql
# or paste it into Supabase Studio → SQL Editor
```

It adds:

- `users.consent_at`, `users.consent_version` — biometric consent is now recorded.
- `attendance_logs.attendance_date`, a generated column in `Asia/Jakarta`, plus
  the `unique_user_per_day` constraint the duplicate guard depends on.
- `match_faces()` using cosine distance, excluding archived members.
- Row Level Security enabled, with `anon` access revoked.

**If the constraint fails to apply**, duplicate rows already exist. Find them:

```sql
select user_id, attendance_date, count(*)
from attendance_logs group by 1, 2 having count(*) > 1;
```

Keep the earliest row per group, delete the rest, then re-run the migration.
These duplicates are the previous UTC-versus-WIB day-boundary bug: someone who
checked in before 07:00 WIB could be recorded twice on the same WIB day.

**Switch `SUPABASE_KEY` to the service_role key.** RLS now blocks `anon`, and
the backend performs its own authorisation. This key is server-side only and is
never sent to a browser.

---

## 2. New required configuration

`core/config.py` validates everything at startup and reports every problem at
once, rather than failing on whichever module happened to import first.

| Variable | Required | Notes |
| :--- | :--- | :--- |
| `KIOSK_TOKEN` | yes | New. Gates registration, manual check-in and member search. |
| `ADMIN_PASSWORD_HASH` | preferred | bcrypt. `ADMIN_PASSWORD` still works but warns on every boot. |
| `SECRET_KEY` | yes | Minimum 32 characters, enforced. |
| `CHURCH_LAT` / `CHURCH_LNG` | when geofencing is on | **No default.** Verify on a map first. |

`ENABLE_GEOFENCE` now defaults to **true**.

### Verify the church coordinates

The code carried `-7.979261, 112.625760`; `tasks/implementation_plan.md` carried
`-7.9734182, 112.6322894`. They are about 965 m apart, well outside any 200 m
radius, so at most one is correct and neither has ever been validated in
enforcement. Open both in a map, pick the right one, and set it explicitly.
Getting this wrong rejects every member standing at the kiosk.

Copy `.env.example` to `.env` and work through it; every entry says what it is
for.

---

## 3. Enrol each kiosk tablet (one-time, per device)

`/api/register`, `/api/attendance/manual-checkin` and `/api/users/search` were
open to the internet. They now require an enrolled device or an admin session.

On each kiosk tablet:

1. Open `/login` and sign in as pengurus.
2. Open `/kiosk/enroll`. It stores a long-lived device cookie and redirects to
   the kiosk.
3. Sign out of the admin session if you wish — the device cookie is independent.

This also fixes the newcomer dead end: `/register` used to demand the admin
password, so a pengurus had to type it on a public tablet in front of the queue.

`/api/recognize` stays open, guarded by geofencing and rate limiting: locking it
would risk nobody being able to check in on a Saturday.

---

## 4. API changes

| Endpoint | Change |
| :--- | :--- |
| `GET /api/users` | Now `{status, data}`; `face_embedding` no longer included. |
| `GET /api/all-logs` | Paginated: `{status, data, total, limit, offset}`. |
| `PUT /api/users/{id}` | Partial update; omitted fields are left alone. 404 for a missing member. |
| `DELETE /api/users/{id}` | Archives. Response says the history is kept. |
| `DELETE /api/users/{id}/biometrics` | **New.** Irreversibly erases face data and phone number. |
| `POST /api/users/{id}/restore` | **New.** Un-archives. |
| `POST /api/register` | Requires `consent=true`; accepts `lat`/`lng`/`accuracy`. |
| check-in responses | New status `already_checked_in`, distinct from `success`. |
| all endpoints | Failures return 4xx/5xx with generic messages; `/api/dashboard-stats` returns 503 rather than 200 with an error body. |
| `GET /healthz` | **New.** Used by the deploy health gate. |

`/static` now serves only `js`, `assets`, `vendor` and `uploads/photobooth`.
`/static/dashboard.html` used to return the dashboard with no session at all.

---

## 5. Deploy

```bash
DOMAIN=absen.contoh.org bash scripts/deploy_vps.sh
```

Set `DOMAIN`. Without HTTPS, browsers block `getUserMedia` and the kiosk camera
will never start, whatever else is configured.

The script now validates `.env` before touching the running service, waits for
`/healthz`, and rolls back to the previous commit if the new version does not
come up. To roll back manually:

```bash
bash scripts/deploy_vps.sh <previous-sha>
```

---

## 6. Recommended, not required

- **Vendor the frontend libraries** so the kiosk survives a wifi outage:
  ```bash
  bash scripts/vendor_assets.sh
  ```
  Then set `window.KP_VENDOR_BASE = '/static/vendor/mediapipe/'` in
  `frontend/index.html` and `frontend/register.html` and point the `<script>`
  tags at `/static/vendor/…`.
- **Redis for rate limiting** (`RATE_LIMIT_STORAGE_URI`) if you ever run more
  than one worker; the in-memory default is per-process.
- **Enable scheduled backups in Supabase.** There are none today: one bad
  `DELETE` loses the whole attendance history permanently.
- **Lighter model** on a 2 GB VPS: `FACE_MODEL_NAME=buffalo_sc` and
  `FACE_DET_SIZE=320`.

---

## 7. Verify

```bash
curl -fsS https://your-host/healthz
```

Then, on the kiosk:

- Scan a registered face → green panel.
- Scan the same face again → **amber** "Sudah Absen Hari Ini" with the original
  time. If this shows green, the client is stale — hard-refresh.
- Block the network briefly → "Cari Nama Manual" must still open.
- Check the dashboard's "Metode Presensi Hari Ini" card. That ratio is the
  measurement for the open question in PRD §11: whether face recognition is
  earning what it costs.
