# Tanya Jawab Live Podcast KP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modul tanya jawab anonim ala Saweria di web KP (FaceID-KP) untuk acara 14 Nov 2026, plus jalur cadangan statis yang bisa diaktifkan dalam kurang dari 5 menit kalau web KP bermasalah.

**Architecture:** Semua aturan bisnis ada di fungsi Postgres `qna_*` (Supabase proyek FaceID-KP). FastAPI hanya membungkus fungsi itu dengan login cookie, rate limit, SSE, dan proxy TTS. Halaman HTML/JS yang sama berbicara lewat adapter (`qna-api-kp.js` atau `qna-api-supabase.js`). Jalur cadangan = halaman yang sama + adapter Supabase yang memanggil RPC langsung, di-deploy ke Netlify.

**Tech Stack:** FastAPI, supabase-py (postgrest), slowapi, httpx, PostgreSQL/plpgsql + pgcrypto, vanilla JS (tanpa build), Web Speech API, Web Audio API, Google Cloud TTS REST, pytest + pytest-playwright.

**Spec:** `docs/superpowers/specs/2026-11-03-podcast-qna-design.md`

## Global Constraints

- Repo kode: `/Users/josetaneo/GKI BROMO/KP/faceID-KP`, dikerjakan di worktree `/Users/josetaneo/GKI BROMO/KP/faceID-KP-qna` branch `feat/qna-podcast`. **Jangan sentuh perubahan yang belum di-commit di checkout utama.**
- Ikuti `CLAUDE.md` repo: satu router per domain, HTML statis per halaman, komentar berbahasa Indonesia yang menjelaskan *kenapa*.
- **Tidak boleh ada I/O Supabase di event loop.** Handler yang memanggil `qna_service` wajib `def`; satu-satunya `async def` adalah stream SSE yang tidak menyentuh DB (`tests/test_no_blocking_io.py` menegakkan ini, dan **setiap rute baru wajib punya entri di `RECIPES`**).
- Python 3.12, `ruff check .` harus hijau (aturan `E9,F,S,B`).
- Panjang pertanyaan 3–300 karakter (setelah trim); jeda 30 detik per `device_id`; rate limit per IP: kirim `60/minute`, vote `300/minute`.
- Status: `masuk`, `disetujui`, `ditolak`, `tampil`, `selesai`. Maksimal satu `tampil`.
- Mode poin: `hiasan` (acak dari 10/20/50/100, teks `Seseorang memberikan N poin!`) dan `upvote` (teks `Seseorang bertanya, N teman ikut penasaran!`, atau `Seseorang bertanya!` kalau 0).
- Flag fitur baru `qna`, bawaan **mati**.
- Fungsi `qna_*` **tidak** bisa dieksekusi `anon` kecuali setelah `scripts/qna_fallback_on.sql` dijalankan.
- Secret key Supabase / API key Google tidak pernah sampai ke browser atau ke URL.
- Setiap commit diakhiri baris `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Freeze deploy: Kamis 12 Nov 2026.

## File Structure

| File | Tanggung jawab |
|---|---|
| `scripts/2026-11-04_qna.sql` | Tabel `qna_*`, RLS, fungsi `qna_*`, grant ke `service_role` saja |
| `scripts/qna_selftest.sql` | Uji fungsi SQL dalam `BEGIN … ROLLBACK` |
| `scripts/qna_set_pin.sql` | Menetapkan PIN admin jalur cadangan (bcrypt) |
| `scripts/qna_fallback_on.sql` / `scripts/qna_fallback_off.sql` | Membuka/menutup `execute` untuk `anon` |
| `services/qna_service.py` | Pemanggil RPC + `QnaError` (pemetaan pesan DB → HTTP) |
| `core/qna_bus.py` | Siaran sinyal "ada perubahan" ke koneksi SSE (in-process) |
| `services/tts_service.py` | Google Cloud TTS |
| `routers/qna.py` | Halaman `/tanya*` + API `/api/qna/*` |
| `core/flags.py` (ubah) | Tambah flag `qna` |
| `main.py` (ubah) | Daftarkan router |
| `frontend/qna/config.js` | Pilihan adapter (ditimpa saat build cadangan) |
| `frontend/qna/qna-common.js` | `Qna.deviceId`, `QnaError`, pesan, `escapeHtml` |
| `frontend/qna/qna-api-kp.js` | Adapter FastAPI + SSE |
| `frontend/qna/qna-api-supabase.js` | Adapter RPC langsung + polling |
| `frontend/qna/qna.css` | Gaya ketiga halaman |
| `frontend/qna/tanya.html` + `jemaat.js` | Halaman jemaat |
| `frontend/qna/tanya-admin.html` + `admin.js` | Halaman admin |
| `frontend/qna/tanya-display.html` + `display.js` | Videotron |
| `scripts/build_qna_standalone.sh` | Bangun folder statis cadangan |
| `scripts/qna_loadtest.py` | Uji beban |
| `tests/test_qna_service.py`, `tests/test_qna_bus.py`, `tests/test_qna_api.py`, `tests/test_tts_service.py`, `tests/test_qna_frontend.py` | Tes |
| `tests/test_no_blocking_io.py` (ubah) | Resep rute baru |
| `PODCAST 14 NOV 26/docs/runbook-hari-h.md` | Prosedur gladi, hari H, dan pindah ke cadangan |

## Kontrak bersama (dipakai banyak task)

**Fungsi Postgres** (semua `security definer`, mengembalikan `jsonb`):

| Fungsi | Hasil | Error (pesan `raise exception`) |
|---|---|---|
| `qna_state()` | `{session_open, points_mode}` | — |
| `qna_submit(p_body text, p_device uuid)` | `{id}` | `session_closed`, `invalid_body`, `invalid_device`, `cooldown:<detik>` |
| `qna_public_list(p_device uuid)` | `[{id, body, created_at, votes, voted, showing}]` (kosong kalau mode ≠ upvote) | — |
| `qna_vote(p_question uuid, p_device uuid, p_on boolean)` | `{votes, voted}` | `invalid_device`, `not_votable` |
| `qna_display()` | `{nonce, tts_engine, question: {id, body, points_text} \| null}` | — |
| `qna_admin_list(p_pin text)` | `{settings: {session_open, points_mode, tts_engine, hidden, show_nonce, updated_at}, questions: [{id, body, status, created_at, shown_at, votes}]}` | `forbidden` |
| `qna_admin_act(p_pin text, p_id uuid, p_action text)` | `{id, action}` | `forbidden`, `not_found`, `invalid_transition` |
| `qna_admin_screen(p_pin text, p_action text)` | settings | `forbidden`, `nothing_showing`, `invalid_action` |
| `qna_admin_settings(p_pin text, p_session_open boolean, p_points_mode text, p_tts_engine text)` | settings | `forbidden`, `mode_locked` |

Admin sah kalau `auth.role() = 'service_role'` (backend KP) **atau** PIN cocok dengan `qna_secret.pin_hash`.

**Bentuk error HTTP (web KP):** `{"status": "error", "code": "<kode>", "message": "<Bahasa Indonesia>", "retry_after": <int|null>}`. Sukses: `{"status": "success", "data": ...}`.

**`window.QnaApi` (JS)** — identik di kedua adapter:
```
state() → {session_open, points_mode}
submit(body) → {id}
publicList() → [{id, body, votes, voted, showing}]
vote(id, on) → {votes, voted}
display() → {nonce, tts_engine, question|null}
tts(text) → Blob | null        (throw = pakai suara browser)
subscribe(onChange(kind), onStatus(bool)) → unsubscribe()
admin.needsLogin: bool, admin.hasPin(), admin.login(pin)
admin.list(), admin.act(id, action), admin.screen(action), admin.settings({session_open?, points_mode?, tts_engine?})
```
Semua error dilempar sebagai `Qna.QnaError` dengan `.code` (kode di atas atau `network`) dan `.retryAfter`.

---

### Task 0: Worktree & lingkungan

**Files:** tidak ada file baru.

- [ ] **Step 1: Buat worktree dari `main`**

```bash
cd "/Users/josetaneo/GKI BROMO/KP/faceID-KP"
git fetch origin
git worktree add "../faceID-KP-qna" -b feat/qna-podcast origin/main
cd "../faceID-KP-qna"
cp ../faceID-KP/.env .env
ln -s ../faceID-KP/venv venv
```

- [ ] **Step 2: Pastikan baseline hijau**

Run: `venv/bin/pytest tests/ --ignore=tests/test_e2e_playwright.py -q`
Expected: semua PASS (catat kalau ada yang memang sudah merah di `main`; jangan diperbaiki di branch ini).

---

### Task 1: Skema & fungsi SQL + uji SQL

**Files:**
- Create: `scripts/2026-11-04_qna.sql`, `scripts/qna_selftest.sql`, `scripts/qna_set_pin.sql`, `scripts/qna_fallback_on.sql`, `scripts/qna_fallback_off.sql`

**Interfaces:**
- Produces: tabel `qna_questions`, `qna_votes`, `qna_settings`, `qna_secret`; fungsi di tabel "Kontrak bersama".

- [ ] **Step 1: Tulis uji SQL dulu (`scripts/qna_selftest.sql`)**

```sql
-- Uji fungsi tanya jawab. Jalankan di Supabase SQL Editor SETELAH
-- 2026-11-04_qna.sql. Semuanya di dalam transaksi yang di-ROLLBACK: aman
-- dijalankan di produksi, tidak ada data yang tertinggal.
-- Lulus = muncul NOTICE "qna_selftest: semua lulus". Gagal = ERROR "GAGAL: ...".
begin;

-- Kondisi awal yang diketahui, apa pun isi tabel sebelumnya.
delete from qna_votes;
delete from qna_questions;
update qna_settings set session_open = false, points_mode = 'hiasan', tts_engine = 'browser',
  hidden = false, show_nonce = 0 where id = 1;
update qna_secret set pin_hash = extensions.crypt('pin-uji-panjang-123', extensions.gen_salt('bf')) where id = 1;
select set_config('request.jwt.claims', '', true);

create function pg_temp.expect_error(p_sql text, p_expected text) returns void
language plpgsql as $$
begin
  execute p_sql;
  raise exception 'GAGAL: "%" seharusnya ditolak dengan "%"', p_sql, p_expected;
exception when others then
  if sqlerrm not like p_expected then raise; end if;
end $$;

create function pg_temp.check(p_ok boolean, p_what text) returns void
language plpgsql as $$
begin
  if not coalesce(p_ok, false) then raise exception 'GAGAL: %', p_what; end if;
end $$;

do $$
declare
  pin constant text := 'pin-uji-panjang-123';
  dev1 constant uuid := 'aaaaaaaa-0000-4000-8000-000000000001';
  dev2 constant uuid := 'aaaaaaaa-0000-4000-8000-000000000002';
  q1 uuid; q2 uuid; r jsonb;
begin
  -- Sesi tutup menolak kiriman
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', 'Halo narasumber', dev1), 'session_closed');

  -- Admin: PIN salah ditolak, PIN benar diterima
  perform pg_temp.expect_error('select qna_admin_settings(''salah'', true, null, null)', 'forbidden');
  perform qna_admin_settings(pin, false, 'upvote', null);
  perform qna_admin_settings(pin, true, null, null);
  perform pg_temp.check((qna_state() ->> 'session_open')::boolean, 'sesi terbuka');
  perform pg_temp.check(qna_state() ->> 'points_mode' = 'upvote', 'mode upvote');

  -- Mode terkunci selama sesi terbuka
  perform pg_temp.expect_error(format('select qna_admin_settings(%L, null, %L, null)', pin, 'hiasan'), 'mode_locked');

  -- Validasi isi
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', '  ab  ', dev1), 'invalid_body');
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', repeat('x', 301), dev1), 'invalid_body');

  -- Kirim + jeda per HP
  q1 := (qna_submit('  Gimana cara tahu panggilan hidup?  ', dev1) ->> 'id')::uuid;
  perform pg_temp.check((select body from qna_questions where id = q1) = 'Gimana cara tahu panggilan hidup?', 'isi di-trim');
  perform pg_temp.check((select status from qna_questions where id = q1) = 'masuk', 'status awal masuk');
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', 'Pertanyaan kedua', dev1), 'cooldown:%');
  q2 := (qna_submit('Kenapa harus ke gereja?', dev2) ->> 'id')::uuid;

  -- Daftar publik hanya yang disetujui; yang masuk tidak bisa didukung
  perform pg_temp.check(jsonb_array_length(qna_public_list(dev1)) = 0, 'pertanyaan masuk tidak publik');
  perform pg_temp.expect_error(format('select qna_vote(%L, %L, true)', q1, dev1), 'not_votable');
  perform qna_admin_act(pin, q1, 'approve');
  r := qna_public_list(dev1);
  perform pg_temp.check(jsonb_array_length(r) = 1, 'satu pertanyaan publik');
  perform pg_temp.check(r -> 0 ->> 'device_id' is null, 'device_id tidak bocor');

  -- Dukungan unik per HP, bisa dibatalkan
  perform qna_vote(q1, dev1, true);
  perform qna_vote(q1, dev1, true);
  perform pg_temp.check((qna_vote(q1, dev2, true) ->> 'votes')::int = 2, 'dua dukungan');
  perform pg_temp.check((qna_vote(q1, dev2, false) ->> 'votes')::int = 1, 'batal dukung');
  perform pg_temp.check((qna_public_list(dev1) -> 0 ->> 'voted')::boolean, 'voted untuk dev1');
  perform pg_temp.check(not (qna_public_list(dev2) -> 0 ->> 'voted')::boolean, 'tidak voted untuk dev2');

  -- Tolak lalu setujui ulang
  perform qna_admin_act(pin, q2, 'reject');
  perform pg_temp.check((select status from qna_questions where id = q2) = 'ditolak', 'ditolak');
  perform qna_admin_act(pin, q2, 'approve');

  -- Tampil: satu saja, nonce naik, teks poin upvote
  perform qna_admin_act(pin, q1, 'show');
  r := qna_display();
  perform pg_temp.check((r ->> 'nonce')::int = 1, 'nonce 1');
  perform pg_temp.check(r -> 'question' ->> 'body' = 'Gimana cara tahu panggilan hidup?', 'display isi q1');
  perform pg_temp.check(r -> 'question' ->> 'points_text' = 'Seseorang bertanya, 1 teman ikut penasaran!', 'teks upvote');
  perform qna_admin_act(pin, q2, 'show');
  perform pg_temp.check((select status from qna_questions where id = q1) = 'selesai', 'q1 otomatis selesai');
  perform pg_temp.check((select count(*) from qna_questions where status = 'tampil') = 1, 'hanya satu tampil');
  perform pg_temp.check(qna_display() -> 'question' ->> 'points_text' = 'Seseorang bertanya!', 'teks upvote nol');

  -- Kosongkan & putar ulang
  perform qna_admin_screen(pin, 'hide');
  r := qna_display();
  perform pg_temp.check(r -> 'question' = 'null'::jsonb and (r ->> 'nonce')::int = 3, 'layar kosong, nonce 3');
  perform qna_admin_screen(pin, 'replay');
  r := qna_display();
  perform pg_temp.check(r -> 'question' ->> 'id' = q2::text and (r ->> 'nonce')::int = 4, 'putar ulang q2');

  -- Selesai
  perform qna_admin_act(pin, q2, 'done');
  perform pg_temp.check(qna_display() -> 'question' = 'null'::jsonb, 'tidak ada yang tampil');
  perform pg_temp.expect_error(format('select qna_admin_screen(%L, %L)', pin, 'replay'), 'nothing_showing');
  perform pg_temp.expect_error(format('select qna_admin_act(%L, %L, %L)', pin, q1, 'done'), 'invalid_transition');
  perform pg_temp.expect_error(format('select qna_admin_act(%L, %L, %L)', pin, gen_random_uuid(), 'approve'), 'not_found');

  -- Mode hiasan: tutup + ganti mode dalam satu panggilan boleh
  perform qna_admin_settings(pin, false, 'hiasan', null);
  perform qna_admin_settings(pin, true, null, null);
  perform qna_admin_act(pin, q1, 'show');
  perform pg_temp.check(qna_display() -> 'question' ->> 'points_text' ~ '^Seseorang memberikan (10|20|50|100) poin!$', 'teks hiasan');
  perform pg_temp.check(jsonb_array_length(qna_public_list(dev1)) = 0, 'daftar publik kosong di mode hiasan');

  -- Jalur backend: service_role tanpa PIN
  perform pg_temp.expect_error('select qna_admin_list(null)', 'forbidden');
  perform set_config('request.jwt.claims', '{"role":"service_role"}', true);
  perform pg_temp.check(jsonb_array_length(qna_admin_list(null) -> 'questions') = 2, 'service_role melihat semua');
  perform set_config('request.jwt.claims', '', true);

  -- Tertutup untuk anon secara bawaan
  perform pg_temp.check(not has_function_privilege('anon', 'qna_submit(text, uuid)', 'execute'), 'anon tidak bisa qna_submit');
  perform pg_temp.check(not has_function_privilege('anon', 'qna_admin_list(text)', 'execute'), 'anon tidak bisa qna_admin_list');
  perform pg_temp.check(not has_table_privilege('anon', 'qna_questions', 'select'), 'anon tidak bisa baca tabel');

  raise notice 'qna_selftest: semua lulus';
end $$;

rollback;
```

- [ ] **Step 2: Jalankan uji SQL untuk melihat gagal**

Jalankan isi `scripts/qna_selftest.sql` di Supabase SQL Editor (proyek FaceID-KP). Bisa juga lewat Supabase MCP `execute_sql`, **setelah user mengizinkan** — ini database produksi, meski transaksinya di-rollback.
Expected: ERROR `relation "qna_votes" does not exist`.

- [ ] **Step 3: Tulis migrasi `scripts/2026-11-04_qna.sql`**

```sql
-- Modul tanya jawab live podcast (spec: PODCAST 14 NOV 26/docs/superpowers/specs/
-- 2026-11-03-podcast-qna-design.md). Dijalankan lewat Supabase SQL Editor. Aman diulang.
--
-- Semua aturan bisnis sengaja ada di fungsi qna_* di sini, bukan di Python:
-- jalur cadangan (situs statis tanpa web KP) memanggil fungsi yang sama
-- langsung dari browser, jadi aturannya tidak boleh hidup di dua tempat.
--
-- Model keamanan sama dengan 2026-10-15_rls_lockdown.sql: RLS menyala tanpa
-- policy. Fungsi hanya bisa dieksekusi service_role (server KP). Peran anon
-- baru mendapat akses saat qna_fallback_on.sql dijalankan.

create extension if not exists pgcrypto with schema extensions;

create table if not exists qna_questions (
  id           uuid primary key default gen_random_uuid(),
  body         text not null check (char_length(body) between 3 and 300),
  status       text not null default 'masuk'
               check (status in ('masuk', 'disetujui', 'ditolak', 'tampil', 'selesai')),
  device_id    uuid not null,  -- hanya untuk jeda & dukungan; tidak pernah dikembalikan ke publik
  decor_points int,
  created_at   timestamptz not null default now(),
  shown_at     timestamptz
);
create index if not exists qna_questions_device_idx on qna_questions (device_id, created_at desc);
-- Videotron hanya punya satu layar.
create unique index if not exists qna_questions_one_showing on qna_questions ((true)) where status = 'tampil';

create table if not exists qna_votes (
  question_id uuid not null references qna_questions (id) on delete cascade,
  device_id   uuid not null,
  created_at  timestamptz not null default now(),
  primary key (question_id, device_id)
);

create table if not exists qna_settings (
  id           int primary key check (id = 1),
  session_open boolean not null default false,
  points_mode  text not null default 'hiasan' check (points_mode in ('hiasan', 'upvote')),
  tts_engine   text not null default 'browser' check (tts_engine in ('browser', 'cloud')),
  hidden       boolean not null default false,
  -- Naik di setiap show/done/hide/replay. Display bereaksi saat nilainya
  -- berubah, jadi SSE dan polling memakai satu mekanisme yang sama.
  show_nonce   int not null default 0,
  updated_at   timestamptz not null default now()
);
insert into qna_settings (id) values (1) on conflict (id) do nothing;

create table if not exists qna_secret (
  id       int primary key check (id = 1),
  pin_hash text  -- bcrypt; diisi lewat qna_set_pin.sql
);
insert into qna_secret (id) values (1) on conflict (id) do nothing;

alter table qna_questions enable row level security;
alter table qna_votes enable row level security;
alter table qna_settings enable row level security;
alter table qna_secret enable row level security;
revoke all on table qna_questions, qna_votes, qna_settings, qna_secret from anon, authenticated;

create or replace function qna__is_admin(p_pin text) returns boolean
language plpgsql security definer set search_path = public, extensions as $$
declare v_hash text;
begin
  -- Server KP memakai secret key: role-nya service_role, tanpa PIN.
  if coalesce(auth.role(), '') = 'service_role' or current_setting('role', true) = 'service_role' then
    return true;
  end if;
  select pin_hash into v_hash from qna_secret where id = 1;
  return v_hash is not null and p_pin is not null and v_hash = crypt(p_pin, v_hash);
end $$;

create or replace function qna_state() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object('session_open', session_open, 'points_mode', points_mode)
  from qna_settings where id = 1
$$;

create or replace function qna_submit(p_body text, p_device uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_body text := btrim(coalesce(p_body, ''));
  v_last timestamptz;
  v_id   uuid;
begin
  if not (select session_open from qna_settings where id = 1) then
    raise exception 'session_closed';
  end if;
  if p_device is null then raise exception 'invalid_device'; end if;
  if char_length(v_body) < 3 or char_length(v_body) > 300 then
    raise exception 'invalid_body';
  end if;
  -- Jeda per HP, bukan per IP: satu WiFi gereja = satu IP (NAT).
  select max(created_at) into v_last from qna_questions where device_id = p_device;
  if v_last is not null and v_last > now() - interval '30 seconds' then
    raise exception 'cooldown:%',
      greatest(1, ceil(extract(epoch from (v_last + interval '30 seconds' - now())))::int);
  end if;
  insert into qna_questions (body, device_id) values (v_body, p_device) returning id into v_id;
  return jsonb_build_object('id', v_id);
end $$;

create or replace function qna_public_list(p_device uuid) returns jsonb
language sql stable security definer set search_path = public as $$
  select coalesce(jsonb_agg(to_jsonb(t) order by t.votes desc, t.created_at), '[]'::jsonb)
  from (
    select q.id, q.body, q.created_at,
           (select count(*) from qna_votes v where v.question_id = q.id)::int as votes,
           exists (select 1 from qna_votes v where v.question_id = q.id and v.device_id = p_device) as voted,
           q.status = 'tampil' as showing
    from qna_questions q
    where q.status in ('disetujui', 'tampil')
      and (select points_mode from qna_settings where id = 1) = 'upvote'
  ) t
$$;

create or replace function qna_vote(p_question uuid, p_device uuid, p_on boolean) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v_status text; v_votes int;
begin
  if p_device is null then raise exception 'invalid_device'; end if;
  select status into v_status from qna_questions where id = p_question;
  if v_status is null or v_status not in ('disetujui', 'tampil')
     or (select points_mode from qna_settings where id = 1) <> 'upvote' then
    raise exception 'not_votable';
  end if;
  if p_on then
    insert into qna_votes (question_id, device_id) values (p_question, p_device) on conflict do nothing;
  else
    delete from qna_votes where question_id = p_question and device_id = p_device;
  end if;
  select count(*) into v_votes from qna_votes where question_id = p_question;
  return jsonb_build_object('votes', v_votes, 'voted', coalesce(p_on, false));
end $$;

create or replace function qna_display() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare s qna_settings; q qna_questions; v_votes int; v_text text;
begin
  select * into s from qna_settings where id = 1;
  select * into q from qna_questions where status = 'tampil';
  if q.id is null or s.hidden then
    return jsonb_build_object('nonce', s.show_nonce, 'tts_engine', s.tts_engine, 'question', null);
  end if;
  if s.points_mode = 'upvote' then
    select count(*) into v_votes from qna_votes where question_id = q.id;
    v_text := case when v_votes > 0
      then format('Seseorang bertanya, %s teman ikut penasaran!', v_votes)
      else 'Seseorang bertanya!' end;
  else
    v_text := format('Seseorang memberikan %s poin!', coalesce(q.decor_points, 10));
  end if;
  return jsonb_build_object('nonce', s.show_nonce, 'tts_engine', s.tts_engine,
    'question', jsonb_build_object('id', q.id, 'body', q.body, 'points_text', v_text));
end $$;

create or replace function qna_admin_list(p_pin text) returns jsonb
language plpgsql stable security definer set search_path = public, extensions as $$
begin
  if not qna__is_admin(p_pin) then raise exception 'forbidden'; end if;
  return jsonb_build_object(
    'settings', (select to_jsonb(s) - 'id' from qna_settings s where id = 1),
    'questions', coalesce((
      select jsonb_agg(to_jsonb(t) order by t.created_at)
      from (
        select q.id, q.body, q.status, q.created_at, q.shown_at,
               (select count(*) from qna_votes v where v.question_id = q.id)::int as votes
        from qna_questions q
      ) t), '[]'::jsonb));
end $$;

create or replace function qna_admin_act(p_pin text, p_id uuid, p_action text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare v_status text;
begin
  if not qna__is_admin(p_pin) then raise exception 'forbidden'; end if;
  select status into v_status from qna_questions where id = p_id for update;
  if v_status is null then raise exception 'not_found'; end if;

  if p_action = 'approve' and v_status in ('masuk', 'ditolak') then
    update qna_questions set status = 'disetujui' where id = p_id;
  elsif p_action = 'reject' and v_status in ('masuk', 'disetujui') then
    update qna_questions set status = 'ditolak' where id = p_id;
  elsif p_action = 'show' and v_status in ('disetujui', 'selesai') then
    -- Yang sedang tampil diturunkan dulu supaya indeks "satu tampil" tidak dilanggar.
    update qna_questions set status = 'selesai' where status = 'tampil';
    update qna_questions
      set status = 'tampil', shown_at = now(),
          decor_points = (array[10, 20, 50, 100])[1 + floor(random() * 4)::int]
      where id = p_id;
    update qna_settings set hidden = false, show_nonce = show_nonce + 1, updated_at = now() where id = 1;
  elsif p_action = 'done' and v_status = 'tampil' then
    update qna_questions set status = 'selesai' where id = p_id;
    update qna_settings set hidden = false, show_nonce = show_nonce + 1, updated_at = now() where id = 1;
  else
    raise exception 'invalid_transition';
  end if;
  return jsonb_build_object('id', p_id, 'action', p_action);
end $$;

create or replace function qna_admin_screen(p_pin text, p_action text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
begin
  if not qna__is_admin(p_pin) then raise exception 'forbidden'; end if;
  if p_action = 'hide' then
    update qna_settings set hidden = true, show_nonce = show_nonce + 1, updated_at = now() where id = 1;
  elsif p_action = 'replay' then
    if not exists (select 1 from qna_questions where status = 'tampil') then
      raise exception 'nothing_showing';
    end if;
    update qna_settings set hidden = false, show_nonce = show_nonce + 1, updated_at = now() where id = 1;
  else
    raise exception 'invalid_action';
  end if;
  return (select to_jsonb(s) - 'id' from qna_settings s where id = 1);
end $$;

create or replace function qna_admin_settings(
  p_pin text, p_session_open boolean default null,
  p_points_mode text default null, p_tts_engine text default null
) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare s qna_settings;
begin
  if not qna__is_admin(p_pin) then raise exception 'forbidden'; end if;
  select * into s from qna_settings where id = 1 for update;
  -- Mengganti mode di tengah sesi membuat poin yang sudah tampil tidak konsisten.
  -- Menutup sesi dan mengganti mode dalam satu panggilan tetap boleh.
  if p_points_mode is not null and p_points_mode <> s.points_mode
     and s.session_open and coalesce(p_session_open, true) then
    raise exception 'mode_locked';
  end if;
  update qna_settings set
    session_open = coalesce(p_session_open, session_open),
    points_mode  = coalesce(p_points_mode, points_mode),
    tts_engine   = coalesce(p_tts_engine, tts_engine),
    updated_at   = now()
  where id = 1
  returning * into s;
  return to_jsonb(s) - 'id';
end $$;

-- Postgres dan Supabase memberi execute ke PUBLIC/anon secara bawaan pada
-- fungsi baru. Dicabut eksplisit; hanya server yang boleh memanggil.
revoke all on function
  qna__is_admin(text), qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
  qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
  qna_admin_act(text, uuid, text), qna_admin_screen(text, text),
  qna_admin_settings(text, boolean, text, text)
  from public, anon, authenticated;
grant execute on function
  qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
  qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
  qna_admin_act(text, uuid, text), qna_admin_screen(text, text),
  qna_admin_settings(text, boolean, text, text)
  to service_role;

notify pgrst, 'reload schema';
```

- [ ] **Step 4: Tulis skrip PIN dan saklar cadangan**

`scripts/qna_set_pin.sql`:
```sql
-- PIN admin untuk jalur cadangan (situs statis). Jalankan saat gladi bersih,
-- simpan frasanya di DUA orang panitia. Minimal 12 karakter: fungsi admin
-- terbuka ke internet selama jalur cadangan aktif.
do $$
declare v_pin constant text := 'GANTI-DENGAN-FRASA-PANJANG';
begin
  if v_pin = 'GANTI-DENGAN-FRASA-PANJANG' or char_length(v_pin) < 12 then
    raise exception 'Ganti v_pin dengan frasa minimal 12 karakter dulu.';
  end if;
  update qna_secret set pin_hash = extensions.crypt(v_pin, extensions.gen_salt('bf')) where id = 1;
end $$;
```

`scripts/qna_fallback_on.sql`:
```sql
-- HARI H, hanya kalau web KP bermasalah: buka fungsi qna_* untuk kunci
-- publishable supaya situs cadangan (Netlify) bisa bekerja. PIN harus sudah
-- diisi lewat qna_set_pin.sql. Matikan lagi dengan qna_fallback_off.sql.
do $$
begin
  if (select pin_hash from qna_secret where id = 1) is null then
    raise exception 'PIN admin belum diisi. Jalankan qna_set_pin.sql dulu.';
  end if;
end $$;
grant execute on function
  qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
  qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
  qna_admin_act(text, uuid, text), qna_admin_screen(text, text),
  qna_admin_settings(text, boolean, text, text)
  to anon;
```

`scripts/qna_fallback_off.sql`:
```sql
-- Tutup lagi jalur cadangan. Jalankan setelah acara (atau setelah web KP pulih).
revoke execute on function
  qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
  qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
  qna_admin_act(text, uuid, text), qna_admin_screen(text, text),
  qna_admin_settings(text, boolean, text, text)
  from anon;
```

- [ ] **Step 5: Terapkan migrasi lalu jalankan uji SQL**

Minta izin user dulu, lalu jalankan `scripts/2026-11-04_qna.sql` disusul `scripts/qna_selftest.sql` di SQL Editor (atau MCP `apply_migration` dengan nama `qna`, lalu `execute_sql`).
Expected: NOTICE `qna_selftest: semua lulus`. Jalankan juga Security Advisor (MCP `get_advisors` type `security`): tidak boleh ada temuan baru `rls_disabled_in_public` untuk tabel `qna_*`.

- [ ] **Step 6: Commit**

```bash
git add scripts/2026-11-04_qna.sql scripts/qna_selftest.sql scripts/qna_set_pin.sql scripts/qna_fallback_on.sql scripts/qna_fallback_off.sql
git commit -m "feat(qna): skema dan fungsi tanya jawab live podcast

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Flag `qna` + `services/qna_service.py`

**Files:**
- Modify: `core/flags.py` (dict `FLAGS`)
- Create: `services/qna_service.py`
- Test: `tests/test_qna_service.py`

**Interfaces:**
- Consumes: fungsi SQL Task 1.
- Produces:
  - `class QnaError(Exception)` dengan `.code: str`, `.status: int`, `.message: str`, `.retry_after: Optional[int]`; `QnaError.from_db_message(msg: str) -> Optional[QnaError]`
  - `get_state() -> dict`, `submit(body: str, device_id: str) -> dict`, `public_list(device_id: str) -> list`, `vote(question_id: str, device_id: str, on: bool) -> dict`, `display() -> dict`, `admin_list() -> dict`, `admin_act(question_id: str, action: str) -> dict`, `admin_screen(action: str) -> dict`, `admin_settings(session_open: Optional[bool] = None, points_mode: Optional[str] = None, tts_engine: Optional[str] = None) -> dict`

- [ ] **Step 1: Tulis tes yang gagal (`tests/test_qna_service.py`)**

```python
"""qna_service hanya penerjemah: nama parameter RPC dan pesan error DB → HTTP.

Aturan bisnisnya sendiri diuji di scripts/qna_selftest.sql.
"""
import pytest
from postgrest.exceptions import APIError

from services import qna_service
from services.qna_service import QnaError


class FakeRpc:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error
        self.calls = []

    def rpc(self, fn, params):
        self.calls.append((fn, params))
        return self

    def execute(self):
        if self.error:
            raise self.error
        return self


def _db_error(message):
    return APIError({"message": message, "code": "P0001", "hint": None, "details": None})


@pytest.fixture
def fake(monkeypatch):
    rpc = FakeRpc(data={})
    monkeypatch.setattr(qna_service, "supabase", rpc)
    return rpc


def test_submit_sends_named_params(fake):
    fake.data = {"id": "abc"}
    assert qna_service.submit("Halo semua", "dev-1") == {"id": "abc"}
    assert fake.calls == [("qna_submit", {"p_body": "Halo semua", "p_device": "dev-1"})]


def test_vote_and_public_list_params(fake):
    fake.data = []
    assert qna_service.public_list("dev-1") == []
    fake.data = {"votes": 1, "voted": True}
    qna_service.vote("q-1", "dev-1", True)
    assert fake.calls == [
        ("qna_public_list", {"p_device": "dev-1"}),
        ("qna_vote", {"p_question": "q-1", "p_device": "dev-1", "p_on": True}),
    ]


def test_admin_calls_send_null_pin_so_db_checks_service_role(fake):
    qna_service.admin_list()
    qna_service.admin_act("q-1", "show")
    qna_service.admin_screen("hide")
    qna_service.admin_settings(session_open=True)
    assert fake.calls == [
        ("qna_admin_list", {"p_pin": None}),
        ("qna_admin_act", {"p_pin": None, "p_id": "q-1", "p_action": "show"}),
        ("qna_admin_screen", {"p_pin": None, "p_action": "hide"}),
        ("qna_admin_settings", {"p_pin": None, "p_session_open": True,
                                "p_points_mode": None, "p_tts_engine": None}),
    ]


def test_cooldown_becomes_429_with_retry_after(fake):
    fake.error = _db_error("cooldown:12")
    with pytest.raises(QnaError) as exc:
        qna_service.submit("Halo semua", "dev-1")
    assert (exc.value.code, exc.value.status, exc.value.retry_after) == ("cooldown", 429, 12)


@pytest.mark.parametrize("message, status", [
    ("session_closed", 409), ("invalid_body", 400), ("invalid_device", 400),
    ("not_votable", 409), ("not_found", 404), ("invalid_transition", 409),
    ("invalid_action", 400), ("mode_locked", 409), ("nothing_showing", 409),
    ("forbidden", 403),
])
def test_known_db_errors_map_to_http_status(fake, message, status):
    fake.error = _db_error(message)
    with pytest.raises(QnaError) as exc:
        qna_service.display()
    assert exc.value.code == message
    assert exc.value.status == status
    assert exc.value.message  # pesan Bahasa Indonesia untuk pengguna


def test_unknown_db_error_is_not_swallowed(fake):
    fake.error = _db_error('relation "qna_settings" does not exist')
    with pytest.raises(APIError):
        qna_service.get_state()


def test_unexpected_shapes_fall_back_to_safe_defaults(fake):
    # FakeSupabase di test_no_blocking_io.py mengembalikan [] untuk semua RPC.
    fake.data = []
    assert qna_service.get_state() == {"session_open": False, "points_mode": "hiasan"}
    assert qna_service.display() == {"nonce": 0, "question": None, "tts_engine": "browser"}
    assert qna_service.admin_list() == {"settings": {}, "questions": []}
    fake.data = None
    assert qna_service.public_list("dev-1") == []


def test_qna_flag_exists_and_defaults_off():
    from core import flags
    assert "qna" in flags.FLAGS
    assert flags._defaults()["qna"] is False
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_service.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'services.qna_service'`

- [ ] **Step 3: Tambah flag di `core/flags.py`** (di dalam dict `FLAGS`, setelah `"registration"`)

```python
    "qna": (
        "Tanya Jawab Podcast",
        lambda: False,
        "Buka halaman /tanya untuk jemaat mengirim pertanyaan. Nyalakan hanya di acara podcast.",
    ),
```

- [ ] **Step 4: Tulis `services/qna_service.py`**

```python
"""Pemanggil fungsi Postgres qna_* untuk modul tanya jawab.

Aturan bisnis (jeda per HP, transisi status, teks poin) ada di
scripts/2026-11-04_qna.sql, bukan di sini: jalur cadangan memanggil fungsi
yang sama langsung dari browser. Modul ini hanya menamai parameter dan
menerjemahkan pesan error DB menjadi status HTTP.

Semua fungsi sinkron (supabase-py) — panggil hanya dari handler `def`.
"""
from typing import Optional

from postgrest.exceptions import APIError

from database import supabase

# kode -> (status HTTP, pesan untuk pengguna)
ERRORS = {
    "session_closed": (409, "Sesi tanya jawab belum dibuka atau sudah ditutup."),
    "cooldown": (429, "Tunggu sebentar sebelum mengirim lagi."),
    "invalid_body": (400, "Pertanyaan harus 3–300 karakter."),
    "invalid_device": (400, "Perangkat tidak dikenali. Muat ulang halaman."),
    "not_votable": (409, "Pertanyaan ini sudah tidak bisa didukung."),
    "not_found": (404, "Pertanyaan tidak ditemukan."),
    "invalid_transition": (409, "Aksi ini tidak berlaku untuk status pertanyaan sekarang."),
    "invalid_action": (400, "Aksi tidak dikenal."),
    "mode_locked": (409, "Tutup sesi dulu sebelum mengganti mode poin."),
    "nothing_showing": (409, "Tidak ada pertanyaan yang sedang tampil."),
    "forbidden": (403, "Akses admin ditolak."),
}

DEFAULT_STATE = {"session_open": False, "points_mode": "hiasan"}
DEFAULT_DISPLAY = {"nonce": 0, "question": None, "tts_engine": "browser"}
DEFAULT_ADMIN_LIST = {"settings": {}, "questions": []}


class QnaError(Exception):
    """Penolakan yang dimengerti pengguna. `code` dipakai frontend."""

    def __init__(self, code: str, retry_after: Optional[int] = None):
        status, message = ERRORS[code]
        super().__init__(code)
        self.code = code
        self.status = status
        self.message = message
        self.retry_after = retry_after

    @classmethod
    def from_db_message(cls, message: str) -> Optional["QnaError"]:
        if message.startswith("cooldown:"):
            try:
                return cls("cooldown", retry_after=max(1, int(message.split(":", 1)[1])))
            except ValueError:
                return cls("cooldown", retry_after=30)
        if message in ERRORS:
            return cls(message)
        return None


def _rpc(fn: str, params: Optional[dict] = None):
    try:
        return supabase.rpc(fn, params or {}).execute().data
    except APIError as e:
        err = QnaError.from_db_message(e.message or "")
        if err is None:
            raise  # error tak dikenal = bug atau DB rusak; biarkan jadi 500 + Sentry
        raise err from None


def _obj(data, default: dict) -> dict:
    return data if isinstance(data, dict) else dict(default)


def _list(data) -> list:
    return data if isinstance(data, list) else []


def get_state() -> dict:
    return _obj(_rpc("qna_state"), DEFAULT_STATE)


def submit(body: str, device_id: str) -> dict:
    return _obj(_rpc("qna_submit", {"p_body": body, "p_device": device_id}), {})


def public_list(device_id: str) -> list:
    return _list(_rpc("qna_public_list", {"p_device": device_id}))


def vote(question_id: str, device_id: str, on: bool) -> dict:
    return _obj(_rpc("qna_vote", {"p_question": question_id, "p_device": device_id, "p_on": on}), {})


def display() -> dict:
    return _obj(_rpc("qna_display"), DEFAULT_DISPLAY)


# p_pin None: fungsi DB mengenali server dari role service_role (secret key).
def admin_list() -> dict:
    return _obj(_rpc("qna_admin_list", {"p_pin": None}), DEFAULT_ADMIN_LIST)


def admin_act(question_id: str, action: str) -> dict:
    return _obj(_rpc("qna_admin_act", {"p_pin": None, "p_id": question_id, "p_action": action}), {})


def admin_screen(action: str) -> dict:
    return _obj(_rpc("qna_admin_screen", {"p_pin": None, "p_action": action}), {})


def admin_settings(session_open: Optional[bool] = None, points_mode: Optional[str] = None,
                   tts_engine: Optional[str] = None) -> dict:
    return _obj(_rpc("qna_admin_settings", {
        "p_pin": None, "p_session_open": session_open,
        "p_points_mode": points_mode, "p_tts_engine": tts_engine,
    }), {})
```

- [ ] **Step 5: Jalankan tes**

Run: `venv/bin/pytest tests/test_qna_service.py tests/test_feature_flags.py -v`
Expected: PASS. Kalau `test_feature_flags.py` menghitung jumlah flag secara eksplisit, perbarui angkanya.

- [ ] **Step 6: Uji asap ke DB sungguhan (memastikan service_role dikenali)**

Run: `venv/bin/python -c "from services import qna_service; print(qna_service.admin_list()['settings'])"`
Expected: dict pengaturan (bukan `QnaError forbidden`). Kalau `forbidden`, berarti server belum memakai secret key; cek `SUPABASE_KEY` di `.env` (harus `sb_secret_...`) sebelum lanjut.

- [ ] **Step 7: Commit**

```bash
git add core/flags.py services/qna_service.py tests/test_qna_service.py
git commit -m "feat(qna): flag qna dan pemanggil fungsi qna_*

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `core/qna_bus.py`

**Files:**
- Create: `core/qna_bus.py`
- Test: `tests/test_qna_bus.py`

**Interfaces:**
- Produces: `subscribe() -> asyncio.Queue` (dipanggil di event loop), `unsubscribe(q: asyncio.Queue) -> None`, `publish(kind: str) -> None` (aman dari thread mana pun), `MAX_QUEUE = 16`.

- [ ] **Step 1: Tulis tes yang gagal (`tests/test_qna_bus.py`)**

```python
import asyncio

from core import qna_bus


def test_publish_from_worker_thread_reaches_subscriber():
    # Handler `def` berjalan di threadpool; SSE menunggu di event loop.
    async def scenario():
        q = qna_bus.subscribe()
        try:
            await asyncio.to_thread(qna_bus.publish, "questions")
            return await asyncio.wait_for(q.get(), timeout=1)
        finally:
            qna_bus.unsubscribe(q)

    assert asyncio.run(scenario()) == "questions"


def test_unsubscribed_queue_gets_nothing():
    async def scenario():
        q = qna_bus.subscribe()
        qna_bus.unsubscribe(q)
        await asyncio.to_thread(qna_bus.publish, "display")
        await asyncio.sleep(0.05)
        return q.qsize()

    assert asyncio.run(scenario()) == 0


def test_slow_client_is_dropped_not_blocking():
    async def scenario():
        q = qna_bus.subscribe()
        try:
            for _ in range(qna_bus.MAX_QUEUE + 10):
                await asyncio.to_thread(qna_bus.publish, "questions")
            await asyncio.sleep(0.05)
            return q.qsize()
        finally:
            qna_bus.unsubscribe(q)

    assert asyncio.run(scenario()) == qna_bus.MAX_QUEUE


def test_publish_without_subscribers_is_noop():
    qna_bus.publish("settings")
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_bus.py -v`
Expected: FAIL `ImportError: cannot import name 'qna_bus'`

- [ ] **Step 3: Tulis `core/qna_bus.py`**

```python
"""Siaran "ada perubahan" ke koneksi SSE admin dan display tanya jawab.

Yang disiarkan hanya jenis perubahannya (questions/display/settings), bukan
datanya: klien mengambil ulang lewat endpoint biasa. Dengan begitu koneksi
SSE tidak pernah menyentuh database, dan klien yang ketinggalan sinyal tetap
benar karena polling cadangan 5 detik membaca keadaan yang sama.

Hanya berlaku dalam satu proses. Produksi memakai satu proses uvicorn
(scripts/deploy_vps.sh); kalau suatu saat multi-worker, polling cadangan
tetap menjaga semuanya berjalan, hanya sedikit lebih lambat.
"""
import asyncio
import threading
from typing import Set, Tuple

MAX_QUEUE = 16

_subscribers: Set[Tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
_lock = threading.Lock()


def subscribe() -> asyncio.Queue:
    """Dipanggil dari dalam event loop (generator SSE)."""
    q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE)
    with _lock:
        _subscribers.add((asyncio.get_running_loop(), q))
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    with _lock:
        for entry in [e for e in _subscribers if e[1] is q]:
            _subscribers.discard(entry)


def _offer(q: asyncio.Queue, kind: str) -> None:
    # Klien lambat cukup kehilangan sinyal: isinya diambil ulang saat ia
    # sempat membaca. Menunggu di sini akan menahan event loop.
    if not q.full():
        q.put_nowait(kind)


def publish(kind: str) -> None:
    """Aman dipanggil dari thread mana pun (handler `def` di threadpool)."""
    with _lock:
        targets = list(_subscribers)
    for loop, q in targets:
        try:
            loop.call_soon_threadsafe(_offer, q, kind)
        except RuntimeError:
            unsubscribe(q)  # loop sudah tertutup
```

- [ ] **Step 4: Jalankan tes**

Run: `venv/bin/pytest tests/test_qna_bus.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/qna_bus.py tests/test_qna_bus.py
git commit -m "feat(qna): siaran perubahan in-process untuk SSE

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: API publik `routers/qna.py`

**Files:**
- Create: `routers/qna.py`
- Modify: `main.py` (import + `app.include_router(qna.router)`)
- Modify: `tests/test_no_blocking_io.py` (`RECIPES`, `PATH_PARAMS`)
- Test: `tests/test_qna_api.py`

**Interfaces:**
- Consumes: `qna_service.*`, `QnaError`, `qna_bus.publish`, `flags.is_enabled("qna")`.
- Produces: `router`, `require_qna_enabled()`, `_call(where, fn, *args, **kwargs)`, rute `GET /api/qna/state`, `POST /api/qna/questions`, `GET /api/qna/questions/public`, `POST /api/qna/questions/{question_id}/vote`, `GET /api/qna/display`.

- [ ] **Step 1: Tulis tes yang gagal (`tests/test_qna_api.py`)**

```python
import pytest
from fastapi.testclient import TestClient

from core import flags
from core.security import COOKIE_NAME, create_access_token
from main import app
from routers import qna as qna_router
from services.qna_service import QnaError

client = TestClient(app)
DEVICE = "11111111-1111-4111-8111-111111111111"
QID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def qna_on(monkeypatch):
    monkeypatch.setattr(flags, "_refresh", lambda: {**flags._defaults(), "qna": True})


@pytest.fixture
def published(monkeypatch):
    kinds = []
    monkeypatch.setattr(qna_router.qna_bus, "publish", kinds.append)
    return kinds


def admin_client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(COOKIE_NAME, create_access_token({"sub": "admin"}))
    return c


def test_public_api_is_404_while_flag_off():
    assert client.get("/api/qna/state").status_code == 404
    res = client.post("/api/qna/questions", json={"body": "Halo semua", "device_id": DEVICE})
    assert res.status_code == 404


def test_state(qna_on, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "get_state",
                        lambda: {"session_open": True, "points_mode": "upvote"})
    res = client.get("/api/qna/state")
    assert res.json() == {"status": "success", "data": {"session_open": True, "points_mode": "upvote"}}


def test_submit_calls_service_and_announces(qna_on, published, monkeypatch):
    seen = []
    monkeypatch.setattr(qna_router.qna_service, "submit",
                        lambda body, dev: seen.append((body, dev)) or {"id": QID})
    res = client.post("/api/qna/questions",
                      json={"body": "Gimana cara tahu panggilan hidup?", "device_id": DEVICE})
    assert res.status_code == 200
    assert res.json()["data"] == {"id": QID}
    assert seen == [("Gimana cara tahu panggilan hidup?", DEVICE)]
    assert published == ["questions"]


def test_cooldown_is_429_with_retry_after_and_no_announcement(qna_on, published, monkeypatch):
    def refuse(*_):
        raise QnaError("cooldown", retry_after=12)
    monkeypatch.setattr(qna_router.qna_service, "submit", refuse)
    res = client.post("/api/qna/questions", json={"body": "Halo semua", "device_id": DEVICE})
    assert res.status_code == 429
    assert res.json()["code"] == "cooldown"
    assert res.json()["retry_after"] == 12
    assert published == []


def test_device_id_must_be_uuid(qna_on):
    res = client.post("/api/qna/questions", json={"body": "Halo semua", "device_id": "bukan-uuid"})
    assert res.status_code == 422


def test_public_list_and_vote(qna_on, published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "public_list",
                        lambda dev: [{"id": QID, "body": "x", "votes": 0, "voted": False, "showing": False}])
    votes = []
    monkeypatch.setattr(qna_router.qna_service, "vote",
                        lambda qid, dev, on: votes.append((qid, dev, on)) or {"votes": 1, "voted": on})
    assert client.get("/api/qna/questions/public", params={"device_id": DEVICE}).json()["data"][0]["id"] == QID
    res = client.post(f"/api/qna/questions/{QID}/vote", json={"device_id": DEVICE, "on": True})
    assert res.json()["data"] == {"votes": 1, "voted": True}
    assert votes == [(QID, DEVICE, True)]
    assert published == ["questions"]


def test_display_is_public_even_while_flag_off(monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "display",
                        lambda: {"nonce": 3, "question": None, "tts_engine": "browser"})
    assert client.get("/api/qna/display").json()["data"]["nonce"] == 3


def test_unexpected_error_is_500_without_internal_details(qna_on, monkeypatch):
    def boom():
        raise RuntimeError("detail-internal-rahasia")
    monkeypatch.setattr(qna_router.qna_service, "get_state", boom)
    res = client.get("/api/qna/state")
    assert res.status_code == 500
    assert "rahasia" not in res.text
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_api.py -v`
Expected: FAIL `ImportError: cannot import name 'qna' from 'routers'`

- [ ] **Step 3: Tulis `routers/qna.py`**

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from core import flags, qna_bus
from core.observability import capture_error
from services import qna_service
from services.qna_service import QnaError

router = APIRouter(tags=["qna"])
limiter = Limiter(key_func=get_remote_address)

# Sengaja `def` untuk semua handler yang memanggil qna_service: supabase-py
# sinkron, dan sebagai `async def` ia membekukan event loop seluruh proses —
# termasuk kiosk absen yang hidup di malam yang sama (lihat routers/users.py).
# Satu-satunya `async def` adalah stream SSE, yang tidak pernah menyentuh DB.

# Satu WiFi gereja = satu IP (NAT, temuan Gibbor H2). Batas per IP hanya
# penahan skrip; anti-spam sesungguhnya jeda 30 detik per HP di qna_submit.
SUBMIT_LIMIT = "60/minute"
VOTE_LIMIT = "300/minute"


class SubmitDto(BaseModel):
    body: str = Field(..., max_length=1000)  # batas 300 ditegakkan di DB setelah trim
    device_id: UUID


class VoteDto(BaseModel):
    device_id: UUID
    on: bool


def require_qna_enabled():
    if not flags.is_enabled("qna"):
        raise HTTPException(status_code=404, detail="Sesi tanya jawab sedang tidak aktif.")


def _error(e: QnaError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={
        "status": "error", "code": e.code, "message": e.message, "retry_after": e.retry_after,
    })


def _call(where: str, fn, *args, **kwargs):
    """Sukses -> dict {"status": "success", ...}; selain itu JSONResponse."""
    try:
        return {"status": "success", "data": fn(*args, **kwargs)}
    except QnaError as e:
        return _error(e)
    except Exception as e:
        capture_error(e, where=f"qna.{where}")
        return JSONResponse(status_code=500, content={
            "status": "error", "code": "server", "message": "Terjadi kesalahan di server.",
        })


def _announce(result, *kinds: str):
    if isinstance(result, dict):
        for kind in kinds:
            qna_bus.publish(kind)
    return result


@router.get("/api/qna/state", dependencies=[Depends(require_qna_enabled)])
def get_state():
    return _call("state", qna_service.get_state)


@router.post("/api/qna/questions", dependencies=[Depends(require_qna_enabled)])
@limiter.limit(SUBMIT_LIMIT)
def submit_question(request: Request, payload: SubmitDto):
    return _announce(_call("submit", qna_service.submit, payload.body, str(payload.device_id)), "questions")


@router.get("/api/qna/questions/public", dependencies=[Depends(require_qna_enabled)])
def public_questions(device_id: UUID):
    return _call("public_list", qna_service.public_list, str(device_id))


@router.post("/api/qna/questions/{question_id}/vote", dependencies=[Depends(require_qna_enabled)])
@limiter.limit(VOTE_LIMIT)
def vote_question(request: Request, question_id: UUID, payload: VoteDto):
    return _announce(
        _call("vote", qna_service.vote, str(question_id), str(payload.device_id), payload.on),
        "questions",
    )


# Publik dan tidak dikunci flag: isinya hanya pertanyaan yang memang sedang
# tampil di videotron, dan display harus tetap jalan walau flag jemaat ditutup.
@router.get("/api/qna/display")
def display_state():
    return _call("display", qna_service.display)
```

- [ ] **Step 4: Daftarkan router di `main.py`**

Ubah baris import router menjadi:
```python
from routers import pages, auth, kiosk, users, analytics, attendance, photobooth, observability, flags, qna
```
dan tambahkan setelah `app.include_router(flags.router)`:
```python
app.include_router(qna.router)
```

- [ ] **Step 5: Tambah resep di `tests/test_no_blocking_io.py`**

Di atas `RECIPES` tambahkan:
```python
QNA_DEVICE = "11111111-1111-4111-8111-111111111111"
```
Di dalam `RECIPES` tambahkan:
```python
    ("GET", "/api/qna/state"): Recipe(),
    ("POST", "/api/qna/questions"): Recipe(lambda: {"json": {"body": "Pertanyaan uji", "device_id": QNA_DEVICE}}),
    ("GET", "/api/qna/questions/public"): Recipe(lambda: {"params": {"device_id": QNA_DEVICE}}),
    ("POST", "/api/qna/questions/{question_id}/vote"): Recipe(lambda: {"json": {"device_id": QNA_DEVICE, "on": True}}),
    ("GET", "/api/qna/display"): Recipe(),
```
Di `PATH_PARAMS` tambahkan:
```python
    "question_id": "22222222-2222-4222-8222-222222222222", "action": "approve", "screen_action": "hide",
```

- [ ] **Step 6: Jalankan tes**

Run: `venv/bin/pytest tests/test_qna_api.py tests/test_no_blocking_io.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add routers/qna.py main.py tests/test_qna_api.py tests/test_no_blocking_io.py
git commit -m "feat(qna): API publik kirim, daftar, dukung, dan display

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: API admin + SSE

**Files:**
- Modify: `routers/qna.py`
- Modify: `tests/test_no_blocking_io.py` (`RECIPES`)
- Test: `tests/test_qna_api.py` (tambah)

**Interfaces:**
- Consumes: Task 4.
- Produces: `event_stream(is_disconnected, max_seconds: float, ping_seconds: float = 15)` (async generator `str`), rute `GET /api/qna/admin/questions`, `POST /api/qna/admin/questions/{question_id}/{action}`, `POST /api/qna/admin/screen/{screen_action}`, `PATCH /api/qna/admin/settings`, `GET /api/qna/admin/stream?max_seconds=`.

- [ ] **Step 1: Tambah tes yang gagal di `tests/test_qna_api.py`**

Tambahkan `import asyncio` dan `from core import qna_bus` ke blok import di atas file, lalu:

```python

def test_admin_routes_need_login():
    for method, url in [
        ("GET", "/api/qna/admin/questions"),
        ("POST", f"/api/qna/admin/questions/{QID}/approve"),
        ("POST", "/api/qna/admin/screen/hide"),
        ("PATCH", "/api/qna/admin/settings"),
        ("GET", "/api/qna/admin/stream"),
    ]:
        assert client.request(method, url, json={}).status_code == 401, url


def test_show_announces_questions_and_display(published, monkeypatch):
    calls = []
    monkeypatch.setattr(qna_router.qna_service, "admin_act",
                        lambda qid, action: calls.append((qid, action)) or {"id": qid, "action": action})
    res = admin_client().post(f"/api/qna/admin/questions/{QID}/show")
    assert res.status_code == 200
    assert calls == [(QID, "show")]
    assert published == ["questions", "display"]


def test_approve_does_not_touch_display(published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "admin_act", lambda qid, action: {"id": qid, "action": action})
    admin_client().post(f"/api/qna/admin/questions/{QID}/approve")
    assert published == ["questions"]


def test_unknown_action_is_400_and_never_reaches_db(published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "admin_act",
                        lambda *_: pytest.fail("aksi tak dikenal tidak boleh sampai ke DB"))
    res = admin_client().post(f"/api/qna/admin/questions/{QID}/hapus")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_action"
    assert published == []


def test_screen_replay_announces_display(published, monkeypatch):
    monkeypatch.setattr(qna_router.qna_service, "admin_screen", lambda action: {"show_nonce": 5})
    assert admin_client().post("/api/qna/admin/screen/replay").status_code == 200
    assert published == ["display"]


def test_settings_patch_sends_only_given_fields(published, monkeypatch):
    seen = []
    monkeypatch.setattr(qna_router.qna_service, "admin_settings", lambda **kw: seen.append(kw) or {})
    res = admin_client().patch("/api/qna/admin/settings", json={"session_open": True})
    assert res.status_code == 200
    assert seen == [{"session_open": True, "points_mode": None, "tts_engine": None}]
    assert published == ["settings", "display"]


def test_settings_rejects_unknown_mode():
    res = admin_client().patch("/api/qna/admin/settings", json={"points_mode": "lelang"})
    assert res.status_code == 422


def test_stream_says_hello_with_sse_headers_and_closes():
    res = admin_client().get("/api/qna/admin/stream", params={"max_seconds": 0})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["x-accel-buffering"] == "no"
    assert "event: hello" in res.text


def test_event_stream_forwards_published_kind_and_pings():
    async def scenario():
        async def connected():
            return False
        gen = qna_router.event_stream(connected, max_seconds=5, ping_seconds=0.2)
        hello = await gen.__anext__()
        await asyncio.to_thread(qna_bus.publish, "display")
        changed = await asyncio.wait_for(gen.__anext__(), timeout=1)
        ping = await asyncio.wait_for(gen.__anext__(), timeout=1)
        await gen.aclose()
        return hello, changed, ping

    hello, changed, ping = asyncio.run(scenario())
    assert hello.startswith("retry: 2000\nevent: hello")
    assert changed == 'event: changed\ndata: {"kind": "display"}\n\n'
    assert ping == ": ping\n\n"
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_api.py -v`
Expected: FAIL (404 untuk rute admin, `AttributeError: event_stream`).

- [ ] **Step 3: Tambahkan ke `routers/qna.py`**

Ubah import di atas file menjadi:
```python
import asyncio
import json
import time
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from core import flags, qna_bus
from core.observability import capture_error
from core.security import check_admin_auth
from services import qna_service
from services.qna_service import QnaError
```

Tambahkan di akhir file:
```python
QUESTION_ACTIONS = {"approve", "reject", "show", "done"}
SCREEN_ACTIONS = {"hide", "replay"}


class SettingsDto(BaseModel):
    session_open: Optional[bool] = None
    points_mode: Optional[Literal["hiasan", "upvote"]] = None
    tts_engine: Optional[Literal["browser", "cloud"]] = None


@router.get("/api/qna/admin/questions", dependencies=[Depends(check_admin_auth)])
def admin_questions():
    return _call("admin_list", qna_service.admin_list)


@router.post("/api/qna/admin/questions/{question_id}/{action}", dependencies=[Depends(check_admin_auth)])
def admin_act(question_id: UUID, action: str):
    if action not in QUESTION_ACTIONS:
        return _error(QnaError("invalid_action"))
    kinds = ("questions", "display") if action in ("show", "done") else ("questions",)
    return _announce(_call("admin_act", qna_service.admin_act, str(question_id), action), *kinds)


@router.post("/api/qna/admin/screen/{screen_action}", dependencies=[Depends(check_admin_auth)])
def admin_screen(screen_action: str):
    if screen_action not in SCREEN_ACTIONS:
        return _error(QnaError("invalid_action"))
    return _announce(_call("admin_screen", qna_service.admin_screen, screen_action), "display")


@router.patch("/api/qna/admin/settings", dependencies=[Depends(check_admin_auth)])
def admin_settings(payload: SettingsDto):
    # "display" ikut disiarkan karena tts_engine dibaca videotron.
    return _announce(
        _call("admin_settings", qna_service.admin_settings, **payload.model_dump()),
        "settings", "display",
    )


async def event_stream(is_disconnected, max_seconds: float, ping_seconds: float = 15):
    """Sinyal perubahan untuk admin & display. Tidak pernah menyentuh DB.

    Ditutup sendiri setelah max_seconds; EventSource menyambung ulang otomatis
    (retry 2 detik). Ping tiap 15 detik menjaga koneksi di bawah batas baca
    nginx (60 detik) dan membuat klien yang sudah pergi cepat ketahuan.
    """
    q = qna_bus.subscribe()
    try:
        yield "retry: 2000\nevent: hello\ndata: {}\n\n"
        deadline = time.monotonic() + max_seconds
        while (remaining := deadline - time.monotonic()) > 0:
            if await is_disconnected():
                break
            try:
                kind = await asyncio.wait_for(q.get(), timeout=min(ping_seconds, remaining))
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            yield f"event: changed\ndata: {json.dumps({'kind': kind})}\n\n"
    finally:
        qna_bus.unsubscribe(q)


@router.get("/api/qna/admin/stream", dependencies=[Depends(check_admin_auth)])
async def admin_stream(request: Request, max_seconds: int = Query(600, ge=0, le=600)):
    return StreamingResponse(
        event_stream(request.is_disconnected, max_seconds),
        media_type="text/event-stream",
        # X-Accel-Buffering: tanpa ini nginx menahan event sampai buffer penuh.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Tambah resep di `tests/test_no_blocking_io.py`**

```python
    ("GET", "/api/qna/admin/questions"): Recipe(admin=True),
    ("POST", "/api/qna/admin/questions/{question_id}/{action}"): Recipe(admin=True),
    ("POST", "/api/qna/admin/screen/{screen_action}"): Recipe(admin=True),
    ("PATCH", "/api/qna/admin/settings"): Recipe(lambda: {"json": {"session_open": True}}, admin=True),
    ("GET", "/api/qna/admin/stream"): Recipe(lambda: {"params": {"max_seconds": 0}}, admin=True),
```

- [ ] **Step 5: Jalankan tes**

Run: `venv/bin/pytest tests/test_qna_api.py tests/test_no_blocking_io.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add routers/qna.py tests/test_qna_api.py tests/test_no_blocking_io.py
git commit -m "feat(qna): API admin dan stream SSE

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: TTS cloud

**Files:**
- Create: `services/tts_service.py`
- Modify: `routers/qna.py`, `tests/test_no_blocking_io.py` (resep + fixture `fake_db`), `.env.example`
- Test: `tests/test_tts_service.py`, `tests/test_qna_api.py` (tambah)

**Interfaces:**
- Produces: `tts_service.synthesize(text: str) -> bytes`, `tts_service.TtsUnavailable`, `tts_service.TIMEOUT_S = 4.0`; rute `POST /api/qna/admin/tts` → `audio/mpeg` atau 503 `{"code": "tts_unavailable"}`.

- [ ] **Step 1: Tulis tes yang gagal (`tests/test_tts_service.py`)**

```python
import base64

import httpx
import pytest

from services import tts_service


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("GOOGLE_TTS_API_KEY", raising=False)
    with pytest.raises(tts_service.TtsUnavailable):
        tts_service.synthesize("Halo")


def test_success_decodes_audio_and_keeps_key_out_of_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", "kunci-uji")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(200, json={"audioContent": base64.b64encode(b"mp3").decode()},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(tts_service.httpx, "post", fake_post)
    assert tts_service.synthesize("Halo") == b"mp3"
    assert "kunci-uji" not in seen["url"]
    assert seen["headers"]["X-Goog-Api-Key"] == "kunci-uji"
    assert seen["json"]["voice"]["languageCode"] == "id-ID"
    assert seen["json"]["input"]["text"] == "Halo"
    assert seen["timeout"] == tts_service.TIMEOUT_S


@pytest.mark.parametrize("failure", [
    lambda url, **_: httpx.Response(403, json={}, request=httpx.Request("POST", url)),
    lambda url, **_: (_ for _ in ()).throw(httpx.ReadTimeout("lambat")),
    lambda url, **_: httpx.Response(200, json={}, request=httpx.Request("POST", url)),
])
def test_any_failure_is_unavailable(monkeypatch, failure):
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", "kunci-uji")
    monkeypatch.setattr(tts_service.httpx, "post", failure)
    with pytest.raises(tts_service.TtsUnavailable):
        tts_service.synthesize("Halo")
```

Tambahkan `from services import tts_service` ke blok import `tests/test_qna_api.py`, lalu:
```python

def test_tts_returns_mp3(monkeypatch):
    monkeypatch.setattr(qna_router.tts_service, "synthesize", lambda text: b"ID3-mp3")
    res = admin_client().post("/api/qna/admin/tts", json={"text": "Seseorang bertanya!"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == b"ID3-mp3"


def test_tts_unavailable_is_503_without_leaking_details(monkeypatch):
    def fail(text):
        raise tts_service.TtsUnavailable("detail-internal-rahasia")
    monkeypatch.setattr(qna_router.tts_service, "synthesize", fail)
    res = admin_client().post("/api/qna/admin/tts", json={"text": "Halo"})
    assert res.status_code == 503
    assert res.json()["code"] == "tts_unavailable"
    assert "rahasia" not in res.text


def test_tts_needs_login():
    assert client.post("/api/qna/admin/tts", json={"text": "Halo"}).status_code == 401
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_tts_service.py tests/test_qna_api.py -k tts -v`
Expected: FAIL `ImportError: cannot import name 'tts_service'`

- [ ] **Step 3: Tulis `services/tts_service.py`**

```python
"""Google Cloud Text-to-Speech untuk alert tanya jawab.

Kunci API hanya hidup di server (.env) dan dikirim lewat header, bukan
query string: pesan error httpx menyertakan URL lengkap, dan URL itu bisa
sampai ke log dan Sentry.
"""
import base64
import os

import httpx

from core.observability import capture_error

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
# Display pindah ke suara browser kalau lebih lama dari ini; menunggu lebih
# lama hanya membuat ruangan hening di depan videotron.
TIMEOUT_S = 4.0


class TtsUnavailable(Exception):
    pass


def synthesize(text: str) -> bytes:
    key = os.getenv("GOOGLE_TTS_API_KEY")
    if not key:
        raise TtsUnavailable("GOOGLE_TTS_API_KEY belum diisi")
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "id-ID", "name": os.getenv("GOOGLE_TTS_VOICE", "id-ID-Wavenet-A")},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    try:
        res = httpx.post(GOOGLE_TTS_URL, headers={"X-Goog-Api-Key": key}, json=body, timeout=TIMEOUT_S)
        res.raise_for_status()
        return base64.b64decode(res.json()["audioContent"])
    except (httpx.HTTPError, KeyError, ValueError) as e:
        capture_error(e, where="qna.tts")
        raise TtsUnavailable("TTS cloud gagal") from e
```

- [ ] **Step 4: Tambah endpoint di `routers/qna.py`**

Import: tambahkan `Response` ke `from fastapi.responses import JSONResponse, Response, StreamingResponse` dan `from services import qna_service, tts_service`.

Di akhir file:
```python
class TtsDto(BaseModel):
    text: str = Field(..., min_length=1, max_length=400)


@router.post("/api/qna/admin/tts", dependencies=[Depends(check_admin_auth)])
def admin_tts(payload: TtsDto):
    try:
        audio = tts_service.synthesize(payload.text)
    except tts_service.TtsUnavailable:
        # Display menganggap ini tanda untuk memakai suara browser.
        return JSONResponse(status_code=503, content={
            "status": "error", "code": "tts_unavailable", "message": "Suara cloud tidak tersedia.",
        })
    return Response(content=audio, media_type="audio/mpeg")
```

- [ ] **Step 5: Resep + jaga tes dari jaringan sungguhan**

Di `RECIPES`:
```python
    ("POST", "/api/qna/admin/tts"): Recipe(lambda: {"json": {"text": "uji"}}, admin=True),
```
Di fixture `fake_db`, sebelum `yield fake`:
```python
    # /api/qna/admin/tts tidak boleh menembak Google sungguhan dari tes.
    monkeypatch.delenv("GOOGLE_TTS_API_KEY", raising=False)
```
Di `.env.example` tambahkan:
```
# Opsional: suara cloud untuk tanya jawab podcast (Google Cloud Text-to-Speech).
GOOGLE_TTS_API_KEY=
GOOGLE_TTS_VOICE=id-ID-Wavenet-A
```

- [ ] **Step 6: Jalankan tes + lint**

Run: `venv/bin/pytest tests/test_tts_service.py tests/test_qna_api.py tests/test_no_blocking_io.py -v && venv/bin/ruff check .`
Expected: PASS, ruff bersih.

- [ ] **Step 7: Commit**

```bash
git add services/tts_service.py routers/qna.py tests/test_tts_service.py tests/test_qna_api.py tests/test_no_blocking_io.py .env.example
git commit -m "feat(qna): proxy TTS Google Cloud dengan jatuh ke suara browser

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Fondasi frontend (config, common, dua adapter, CSS) + harness uji browser

**Files:**
- Create: `frontend/qna/config.js`, `frontend/qna/qna-common.js`, `frontend/qna/qna-api-kp.js`, `frontend/qna/qna-api-supabase.js`, `frontend/qna/qna.css`
- Test: `tests/test_qna_frontend.py`

**Interfaces:**
- Produces: `window.QNA_CONFIG = {backend, pages: {jemaat, admin, display}, supabaseUrl?, supabaseKey?}`, `window.Qna`, `window.QnaApi` (lihat "Kontrak bersama"). Harness tes: fixture `backend` (FakeBackend) dan `BASE = "https://qna.test"`.

- [ ] **Step 1: Tulis `frontend/qna/config.js`**

```js
// Jalur utama: web KP. scripts/build_qna_standalone.sh menimpa file ini
// untuk jalur cadangan (adapter Supabase).
window.QNA_CONFIG = {
  backend: "kp",
  pages: { jemaat: "/tanya", admin: "/tanya/admin", display: "/tanya/display" },
};
```

- [ ] **Step 2: Tulis `frontend/qna/qna-common.js`**

```js
// Bagian bersama halaman tanya jawab: identitas HP, error, dan escape HTML.
(function () {
  const DEVICE_KEY = "qna_device_id";
  let memoryDevice = null;

  function deviceId() {
    try {
      let id = localStorage.getItem(DEVICE_KEY);
      if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem(DEVICE_KEY, id);
      }
      return id;
    } catch {
      // Mode privat / penyimpanan diblokir: tetap bisa kirim, hanya jeda dan
      // dukungan tidak bertahan setelah halaman dimuat ulang.
      memoryDevice = memoryDevice || crypto.randomUUID();
      return memoryDevice;
    }
  }

  const MESSAGES = {
    session_closed: "Sesi tanya jawab belum dibuka atau sudah ditutup.",
    cooldown: "Tunggu sebentar sebelum mengirim lagi.",
    invalid_body: "Pertanyaan harus 3–300 karakter.",
    invalid_device: "Perangkat tidak dikenali. Muat ulang halaman.",
    not_votable: "Pertanyaan ini sudah tidak bisa didukung.",
    not_found: "Pertanyaan tidak ditemukan.",
    invalid_transition: "Aksi ini tidak berlaku untuk status pertanyaan sekarang.",
    invalid_action: "Aksi tidak dikenal.",
    mode_locked: "Tutup sesi dulu sebelum mengganti mode poin.",
    nothing_showing: "Tidak ada pertanyaan yang sedang tampil.",
    forbidden: "Akses admin ditolak. Masuk lagi.",
    tts_unavailable: "Suara cloud tidak tersedia.",
    network: "Gagal terhubung. Coba lagi.",
  };

  class QnaError extends Error {
    constructor(code, message, retryAfter) {
      const known = code in MESSAGES ? code : "network";
      super(message || MESSAGES[known]);
      this.code = known;
      this.retryAfter = retryAfter || null;
    }
  }

  // Pesan dari fungsi Postgres: "cooldown:12" atau kode polos seperti "session_closed".
  function parseServerMessage(message) {
    const text = String(message || "");
    if (text.startsWith("cooldown:")) {
      return { code: "cooldown", retryAfter: parseInt(text.slice(9), 10) || 30 };
    }
    return { code: text in MESSAGES ? text : "network", retryAfter: null };
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  window.Qna = { deviceId, MESSAGES, QnaError, parseServerMessage, escapeHtml };
})();
```

- [ ] **Step 3: Tulis `frontend/qna/qna-api-kp.js`**

```js
// Adapter jalur utama: FastAPI web KP (cookie admin + SSE).
(function () {
  if (window.QNA_CONFIG.backend !== "kp") return;
  const { QnaError } = window.Qna;

  async function request(method, url, body) {
    let res;
    try {
      res = await fetch(url, {
        method,
        credentials: "same-origin",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new QnaError("network");
    }
    if (res.status === 401) throw new QnaError("forbidden");
    if (res.ok && (res.headers.get("content-type") || "").startsWith("audio/")) return res.blob();
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      const code = json.code || (res.status === 429 ? "cooldown" : "network");
      throw new QnaError(code, json.message, json.retry_after);
    }
    return json.data;
  }

  function subscribe(onChange, onStatus) {
    const es = new EventSource("/api/qna/admin/stream");
    es.addEventListener("hello", () => { onStatus(true); onChange("all"); });
    es.addEventListener("changed", (e) => onChange(JSON.parse(e.data).kind));
    es.onerror = () => onStatus(false); // EventSource menyambung ulang sendiri
    // Cadangan kalau SSE tertahan proxy atau sinyal terlewat.
    const poll = setInterval(() => onChange("poll"), 5000);
    return () => { es.close(); clearInterval(poll); };
  }

  const device = () => window.Qna.deviceId();
  const enc = encodeURIComponent;

  window.QnaApi = {
    state: () => request("GET", "/api/qna/state"),
    submit: (body) => request("POST", "/api/qna/questions", { body, device_id: device() }),
    publicList: () => request("GET", `/api/qna/questions/public?device_id=${enc(device())}`),
    vote: (id, on) => request("POST", `/api/qna/questions/${enc(id)}/vote`, { device_id: device(), on }),
    display: () => request("GET", "/api/qna/display"),
    tts: (text) => request("POST", "/api/qna/admin/tts", { text }),
    subscribe,
    admin: {
      needsLogin: false, // login lewat /login web KP (cookie)
      hasPin: () => true,
      login: async () => {},
      list: () => request("GET", "/api/qna/admin/questions"),
      act: (id, action) => request("POST", `/api/qna/admin/questions/${enc(id)}/${enc(action)}`),
      screen: (action) => request("POST", `/api/qna/admin/screen/${enc(action)}`),
      settings: (patch) => request("PATCH", "/api/qna/admin/settings", patch),
    },
  };
})();
```

- [ ] **Step 4: Tulis `frontend/qna/qna-api-supabase.js`**

```js
// Adapter jalur cadangan: memanggil fungsi qna_* langsung lewat PostgREST
// dengan publishable key. Tanpa SSE — admin dan display polling tiap 2 detik.
// Hanya berfungsi setelah scripts/qna_fallback_on.sql dijalankan.
(function () {
  const cfg = window.QNA_CONFIG;
  if (cfg.backend !== "supabase") return;
  const { QnaError, parseServerMessage } = window.Qna;
  const PIN_KEY = "qna_admin_pin";
  let memoryPin = null;

  function pin() {
    try { return sessionStorage.getItem(PIN_KEY) || memoryPin; } catch { return memoryPin; }
  }
  function savePin(value) {
    memoryPin = value;
    try {
      if (value) sessionStorage.setItem(PIN_KEY, value);
      else sessionStorage.removeItem(PIN_KEY);
    } catch { /* cukup di memori */ }
  }

  async function rpc(fn, args) {
    let res;
    try {
      res = await fetch(`${cfg.supabaseUrl}/rest/v1/rpc/${fn}`, {
        method: "POST",
        headers: { apikey: cfg.supabaseKey, "Content-Type": "application/json" },
        body: JSON.stringify(args || {}),
      });
    } catch {
      throw new QnaError("network");
    }
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const parsed = parseServerMessage(json && json.message);
      throw new QnaError(parsed.code, null, parsed.retryAfter);
    }
    return json;
  }

  function subscribe(onChange, onStatus) {
    onStatus(true);
    onChange("all");
    const id = setInterval(() => onChange("poll"), 2000);
    return () => clearInterval(id);
  }

  const device = () => window.Qna.deviceId();
  const admin = (fn, args) => rpc(fn, { p_pin: pin(), ...args });

  window.QnaApi = {
    state: () => rpc("qna_state"),
    submit: (body) => rpc("qna_submit", { p_body: body, p_device: device() }),
    publicList: () => rpc("qna_public_list", { p_device: device() }),
    vote: (id, on) => rpc("qna_vote", { p_question: id, p_device: device(), p_on: on }),
    display: () => rpc("qna_display"),
    tts: async () => null, // TTS cloud butuh server; display memakai suara browser
    subscribe,
    admin: {
      needsLogin: true,
      hasPin: () => !!pin(),
      async login(value) {
        savePin(value);
        try {
          await admin("qna_admin_list", {});
        } catch (err) {
          savePin(null);
          throw err;
        }
      },
      list: () => admin("qna_admin_list", {}),
      act: (id, action) => admin("qna_admin_act", { p_id: id, p_action: action }),
      screen: (action) => admin("qna_admin_screen", { p_action: action }),
      settings: (patch) => admin("qna_admin_settings", {
        p_session_open: patch.session_open ?? null,
        p_points_mode: patch.points_mode ?? null,
        p_tts_engine: patch.tts_engine ?? null,
      }),
    },
  };
})();
```

- [ ] **Step 5: Tulis `frontend/qna/qna.css`**

```css
:root {
  --bg: #0f1020;
  --surface: #1a1b33;
  --surface-2: #26284f;
  --text: #f4f3ff;
  --muted: #a9a8c9;
  --accent: #ffb703;
  --accent-ink: #1b1300;
  --accent-2: #ff5d8f;
  --ok: #3ddc97;
  --err: #ff6b6b;
  --radius: 16px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; font-family: var(--font); background: var(--bg); color: var(--text); }
a { color: var(--accent); }
button {
  font: inherit; cursor: pointer; border: 0; border-radius: 999px;
  padding: .65rem 1.15rem; background: var(--surface-2); color: var(--text);
}
button.primary { background: var(--accent); color: var(--accent-ink); font-weight: 700; }
button:disabled { opacity: .5; cursor: not-allowed; }
input, select, textarea {
  font: inherit; color: var(--text); background: var(--bg);
  border: 1px solid var(--surface-2); border-radius: 12px; padding: .6rem .8rem;
}
.muted { color: var(--muted); }
.card { background: var(--surface); border-radius: var(--radius); padding: 1.25rem; }
.conn { width: 10px; height: 10px; border-radius: 50%; background: var(--err); display: inline-block; flex: none; }
.conn.on { background: var(--ok); }

/* Jemaat */
.wrap { max-width: 560px; margin: 0 auto; padding: 24px 16px 48px; display: grid; gap: 16px; }
.eyebrow { text-transform: uppercase; letter-spacing: .12em; font-size: .75rem; color: var(--accent); margin: 0; }
h1 { margin: .25rem 0; font-size: clamp(1.8rem, 6vw, 2.4rem); }
textarea { width: 100%; margin-top: .5rem; resize: vertical; }
.row { display: flex; justify-content: space-between; align-items: center; margin-top: .75rem; gap: 12px; }
#msg { min-height: 1.4em; margin: .75rem 0 0; }
#msg.ok { color: var(--ok); }
#msg.err { color: var(--err); }
.tabs { display: flex; gap: 8px; }
.tabs button.active { background: var(--accent); color: var(--accent-ink); }
.qlist { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.qitem {
  display: flex; gap: 12px; align-items: flex-start; justify-content: space-between;
  background: var(--surface); border-radius: 12px; padding: 1rem;
}
.qitem p { margin: 0; overflow-wrap: anywhere; }
.qitem.showing { outline: 2px solid var(--accent); }
.vote { flex: none; }
.vote.on { background: var(--accent-2); }

/* Admin */
body.admin { padding: 16px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 16px; }
.board { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.col h2 { font-size: 1rem; margin: 12px 0 8px; display: flex; gap: 8px; align-items: center; }
.col .qitem { flex-direction: column; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.toast {
  position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
  background: var(--err); color: #fff; padding: .6rem 1rem; border-radius: 999px;
}
.setup { max-width: 480px; margin: 10vh auto; display: grid; gap: 12px; }

/* Display */
body.display.mode-overlay { background: transparent; }
body.display.mode-full { background: radial-gradient(circle at 20% 20%, #2b2d6e, var(--bg) 60%); min-height: 100vh; }
.stage { position: fixed; inset: 0; display: flex; align-items: flex-end; justify-content: center; padding: 4vh 4vw; }
.mode-full .stage { align-items: center; }
.alert {
  width: min(1100px, 92vw); background: rgba(20, 20, 45, .92); border: 3px solid var(--accent);
  border-radius: 28px; padding: 3vh 3vw; box-shadow: 0 20px 60px rgba(0, 0, 0, .45);
  animation: pop .6s cubic-bezier(.2, 1.4, .4, 1);
}
.points { margin: 0 0 1vh; color: var(--accent); font-weight: 800; font-size: clamp(1.2rem, 3vw, 2.6rem); }
.qbody { margin: 0; font-size: clamp(1.4rem, 4vw, 3.6rem); line-height: 1.25; overflow-wrap: anywhere; }
body.display > .conn { position: fixed; top: 10px; right: 10px; opacity: .6; }
@keyframes pop { from { transform: translateY(40px) scale(.9); opacity: 0; } to { transform: none; opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .alert { animation: none; } }
```

- [ ] **Step 6: Tulis harness uji browser `tests/test_qna_frontend.py`** (dipakai Task 8–10 dan 12)

```python
"""Uji halaman tanya jawab di browser sungguhan tanpa server dan tanpa database.

Semua request ke https://qna.test dijawab di sini: HTML/JS/CSS dibaca dari
frontend/qna, dan /api/qna/* dijawab FakeBackend yang menyimpan state di
memori. Yang diuji adalah perilaku halaman dan adapter, bukan server (server
diuji di test_qna_api.py, aturan bisnis di scripts/qna_selftest.sql).
https dipakai karena crypto.randomUUID hanya ada di secure context.
"""
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from playwright.sync_api import Page, Route, expect

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "qna"
BASE = "https://qna.test"
PAGES = {"/tanya": "tanya.html", "/tanya/admin": "tanya-admin.html", "/tanya/display": "tanya-display.html"}


def ok(data):
    return 200, {"status": "success", "data": data}


def err(status, code, **extra):
    return status, {"status": "error", "code": code, "message": code, **extra}


class FakeBackend:
    def __init__(self):
        self.settings = {"session_open": True, "points_mode": "hiasan", "tts_engine": "browser",
                         "hidden": False, "show_nonce": 0}
        self.questions = []
        self.submitted = []

    def add(self, body, status="masuk", votes=0):
        qid = f"00000000-0000-4000-8000-{len(self.questions) + 1:012d}"
        self.questions.append({"id": qid, "body": body, "status": status, "votes": votes, "voters": set(),
                               "created_at": f"2026-11-14T10:00:{len(self.questions):02d}+00:00", "shown_at": None})
        return qid

    def _q(self, qid):
        return next(q for q in self.questions if q["id"] == qid)

    def act(self, qid, action):
        q = self._q(qid)
        if action == "approve":
            q["status"] = "disetujui"
        elif action == "reject":
            q["status"] = "ditolak"
        elif action == "show":
            for other in self.questions:
                if other["status"] == "tampil":
                    other["status"] = "selesai"
            q["status"], q["shown_at"] = "tampil", "2026-11-14T11:00:00+00:00"
            self.settings.update(hidden=False, show_nonce=self.settings["show_nonce"] + 1)
        elif action == "done":
            q["status"] = "selesai"
            self.settings["show_nonce"] += 1

    def screen(self, action):
        self.settings.update(hidden=(action == "hide"), show_nonce=self.settings["show_nonce"] + 1)

    def display(self):
        q = next((q for q in self.questions if q["status"] == "tampil"), None)
        base = {"nonce": self.settings["show_nonce"], "tts_engine": "browser"}
        if not q or self.settings["hidden"]:
            return {**base, "question": None}
        return {**base, "question": {"id": q["id"], "body": q["body"], "points_text": "Seseorang memberikan 50 poin!"}}

    def public(self, device):
        items = [q for q in self.questions if q["status"] in ("disetujui", "tampil")]
        items.sort(key=lambda q: -q["votes"])
        return [{"id": q["id"], "body": q["body"], "votes": q["votes"], "voted": device in q["voters"],
                 "showing": q["status"] == "tampil"} for q in items]

    def handle(self, method, path, query, body):
        if path == "/api/qna/state":
            return ok({k: self.settings[k] for k in ("session_open", "points_mode")})
        if path == "/api/qna/questions" and method == "POST":
            if not self.settings["session_open"]:
                return err(409, "session_closed")
            self.submitted.append(body)
            return ok({"id": self.add(body["body"])})
        if path == "/api/qna/questions/public":
            return ok(self.public(query.get("device_id")))
        m = re.fullmatch(r"/api/qna/questions/([^/]+)/vote", path)
        if m:
            q = self._q(m.group(1))
            (q["voters"].add if body["on"] else q["voters"].discard)(body["device_id"])
            q["votes"] = len(q["voters"])
            return ok({"votes": q["votes"], "voted": body["on"]})
        if path == "/api/qna/display":
            return ok(self.display())
        if path == "/api/qna/admin/questions":
            return ok({"settings": dict(self.settings),
                       "questions": [{k: v for k, v in q.items() if k != "voters"} for q in self.questions]})
        m = re.fullmatch(r"/api/qna/admin/questions/([^/]+)/(\w+)", path)
        if m:
            self.act(m.group(1), m.group(2))
            return ok({"id": m.group(1), "action": m.group(2)})
        m = re.fullmatch(r"/api/qna/admin/screen/(\w+)", path)
        if m:
            self.screen(m.group(1))
            return ok(dict(self.settings))
        if path == "/api/qna/admin/settings":
            for key, value in body.items():
                if value is not None:
                    self.settings[key] = value
            return ok(dict(self.settings))
        if path == "/api/qna/admin/tts":
            return err(503, "tts_unavailable")
        return 404, {"detail": "tidak ada"}


def serve_static(route: Route, path: str) -> bool:
    if path in PAGES:
        route.fulfill(path=ROOT / PAGES[path])
        return True
    if path.startswith("/static/qna/"):
        route.fulfill(path=ROOT / path.removeprefix("/static/qna/"))
        return True
    return False


@pytest.fixture
def backend(page: Page):
    fake = FakeBackend()

    def handler(route: Route):
        req = route.request
        url = urlsplit(req.url)
        if serve_static(route, url.path):
            return
        if url.path == "/api/qna/admin/stream":
            # retry pendek: EventSource tersambung ulang terus, setiap hello = muat ulang.
            route.fulfill(status=200, content_type="text/event-stream", body="retry: 300\nevent: hello\ndata: {}\n\n")
            return
        body = json.loads(req.post_data) if req.post_data else None
        status, payload = fake.handle(req.method, url.path, dict(parse_qsl(url.query)), body)
        route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))

    page.route(f"{BASE}/**", handler)
    return fake
```

- [ ] **Step 7: Commit**

```bash
git add frontend/qna tests/test_qna_frontend.py
git commit -m "feat(qna): adapter KP/Supabase, gaya, dan harness uji browser

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Halaman jemaat `/tanya`

**Files:**
- Create: `frontend/qna/tanya.html`, `frontend/qna/jemaat.js`
- Modify: `routers/qna.py` (rute halaman), `tests/test_no_blocking_io.py` (resep)
- Test: `tests/test_qna_frontend.py`, `tests/test_qna_api.py` (tambah)

**Interfaces:**
- Consumes: `QnaApi.state/submit/publicList/vote`, `Qna.escapeHtml`.
- Produces: elemen `#body`, `#send`, `#msg`, `#count`, `#closed`, `#form`, `#tabs` (tombol `[data-tab=kirim|daftar]`), `#list` (`.qitem`, `.vote` dengan `<span>` jumlah), `#empty`.

- [ ] **Step 1: Tulis tes yang gagal**

Di `tests/test_qna_frontend.py`:
```python
def test_jemaat_sends_question_then_cools_down(page: Page, backend):
    page.goto(f"{BASE}/tanya")
    page.fill("#body", "Gimana cara tahu panggilan hidup?")
    expect(page.locator("#count")).to_have_text("33/300")
    page.click("#send")
    expect(page.locator("#msg")).to_contain_text("Terkirim")
    expect(page.locator("#send")).to_be_disabled()
    expect(page.locator("#send")).to_contain_text("Tunggu")
    assert backend.submitted[0]["body"] == "Gimana cara tahu panggilan hidup?"
    assert re.fullmatch(r"[0-9a-f-]{36}", backend.submitted[0]["device_id"])


def test_jemaat_sees_closed_notice(page: Page, backend):
    backend.settings["session_open"] = False
    page.goto(f"{BASE}/tanya")
    expect(page.locator("#closed")).to_be_visible()
    expect(page.locator("#form")).to_be_hidden()


def test_tabs_hidden_in_hiasan_mode(page: Page, backend):
    page.goto(f"{BASE}/tanya")
    expect(page.locator("#form")).to_be_visible()
    expect(page.locator("#tabs")).to_be_hidden()


def test_upvote_lists_only_approved_and_toggles_vote(page: Page, backend):
    backend.settings["points_mode"] = "upvote"
    backend.add("Masih menunggu", "masuk")
    backend.add("Sudah disetujui", "disetujui")
    page.goto(f"{BASE}/tanya")
    page.click("[data-tab=daftar]")
    expect(page.locator(".qitem")).to_have_count(1)
    expect(page.locator(".qitem")).to_contain_text("Sudah disetujui")
    page.click(".vote")
    expect(page.locator(".vote span")).to_have_text("1")
    expect(page.locator(".vote")).to_have_class(re.compile(r"\bon\b"))
    page.click(".vote")
    expect(page.locator(".vote span")).to_have_text("0")


def test_question_text_is_escaped(page: Page, backend):
    backend.settings["points_mode"] = "upvote"
    backend.add('<img src=x onerror="window.__xss=1">', "disetujui")
    page.goto(f"{BASE}/tanya")
    page.click("[data-tab=daftar]")
    expect(page.locator(".qitem")).to_contain_text("<img src=x")
    assert page.evaluate("window.__xss") is None
```

Di `tests/test_qna_api.py`:
```python
def test_jemaat_page_404_while_flag_off_and_served_when_on(monkeypatch):
    assert client.get("/tanya").status_code == 404
    monkeypatch.setattr(flags, "_refresh", lambda: {**flags._defaults(), "qna": True})
    flags._cache = {}
    res = client.get("/tanya")
    assert res.status_code == 200
    assert "Tanya narasumber" in res.text
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_frontend.py tests/test_qna_api.py -k "jemaat or upvote or escaped or tabs" -v`
Expected: FAIL (file `tanya.html` tidak ada / 404).

- [ ] **Step 3: Tulis `frontend/qna/tanya.html`**

```html
<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tanya Narasumber · KP GKI Bromo</title>
  <link rel="stylesheet" href="/static/qna/qna.css">
</head>
<body>
  <main class="wrap">
    <header>
      <p class="eyebrow">Live Podcast KP</p>
      <h1>Tanya narasumber</h1>
      <p class="muted">Anonim. Nama dan nomor kamu tidak dicatat.</p>
    </header>

    <nav id="tabs" class="tabs" hidden>
      <button type="button" data-tab="kirim" class="active">Kirim</button>
      <button type="button" data-tab="daftar">Pertanyaan</button>
    </nav>

    <section id="closed" class="card" hidden>
      <p>Sesi tanya jawab belum dibuka. Halaman ini otomatis siap begitu sesi dimulai.</p>
    </section>

    <section id="tab-kirim">
      <form id="form" class="card" hidden>
        <label for="body">Pertanyaanmu</label>
        <textarea id="body" maxlength="300" rows="5" required
                  placeholder="Tulis pertanyaan untuk narasumber…"></textarea>
        <div class="row">
          <span id="count" class="muted">0/300</span>
          <button id="send" type="submit" class="primary">Kirim</button>
        </div>
        <p id="msg" role="status"></p>
      </form>
    </section>

    <section id="tab-daftar" hidden>
      <p class="muted">Dukung pertanyaan teman yang juga ingin kamu dengar jawabannya.</p>
      <ul id="list" class="qlist"></ul>
      <p id="empty" class="muted">Belum ada pertanyaan yang disetujui.</p>
    </section>
  </main>

  <script src="/static/qna/config.js"></script>
  <script src="/static/qna/qna-common.js"></script>
  <script src="/static/qna/qna-api-kp.js"></script>
  <script src="/static/qna/qna-api-supabase.js"></script>
  <script src="/static/qna/jemaat.js"></script>
</body>
</html>
```

- [ ] **Step 4: Tulis `frontend/qna/jemaat.js`**

```js
(function () {
  const $ = (id) => document.getElementById(id);
  let state = { session_open: false, points_mode: "hiasan" };
  let cooling = false;

  function say(text, kind) {
    $("msg").textContent = text;
    $("msg").className = kind || "";
  }

  function updateCount() {
    $("count").textContent = `${$("body").value.length}/300`;
  }

  function showTab(name) {
    for (const b of $("tabs").querySelectorAll("button")) b.classList.toggle("active", b.dataset.tab === name);
    $("tab-kirim").hidden = name !== "kirim";
    $("tab-daftar").hidden = name !== "daftar";
    if (name === "daftar") refreshList();
  }

  async function refreshState() {
    try { state = await QnaApi.state(); } catch { return; }
    $("closed").hidden = state.session_open;
    $("form").hidden = !state.session_open;
    const upvote = state.points_mode === "upvote";
    $("tabs").hidden = !upvote;
    if (!upvote && !$("tab-daftar").hidden) showTab("kirim");
  }

  async function refreshList() {
    if (state.points_mode !== "upvote" || $("tab-daftar").hidden) return;
    let items;
    try { items = await QnaApi.publicList(); } catch { return; }
    $("empty").hidden = items.length > 0;
    $("list").innerHTML = items.map((q) => `
      <li class="qitem${q.showing ? " showing" : ""}">
        <p>${Qna.escapeHtml(q.body)}</p>
        <button type="button" class="vote${q.voted ? " on" : ""}" data-id="${Qna.escapeHtml(q.id)}"
                data-on="${q.voted ? "0" : "1"}" aria-pressed="${q.voted}">▲ <span>${q.votes}</span></button>
      </li>`).join("");
  }

  function startCooldown(seconds) {
    cooling = true;
    let left = seconds;
    const tick = () => {
      if (left <= 0) {
        cooling = false;
        $("send").disabled = false;
        $("send").textContent = "Kirim";
        return;
      }
      $("send").disabled = true;
      $("send").textContent = `Tunggu ${left} dtk`;
      left -= 1;
      setTimeout(tick, 1000);
    };
    tick();
  }

  $("body").addEventListener("input", updateCount);

  $("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (cooling) return;
    const body = $("body").value.trim();
    if (body.length < 3) return say(Qna.MESSAGES.invalid_body, "err");
    $("send").disabled = true;
    try {
      await QnaApi.submit(body);
      $("body").value = "";
      updateCount();
      say("Terkirim! Pertanyaanmu menunggu dipilih panitia.", "ok");
      startCooldown(30);
    } catch (err) {
      say(err.message, "err");
      if (err.code === "cooldown") startCooldown(err.retryAfter || 30);
      else $("send").disabled = false;
      if (err.code === "session_closed") refreshState();
    }
  });

  $("tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-tab]");
    if (b) showTab(b.dataset.tab);
  });

  $("list").addEventListener("click", async (e) => {
    const btn = e.target.closest(".vote");
    if (!btn) return;
    btn.disabled = true;
    try { await QnaApi.vote(btn.dataset.id, btn.dataset.on === "1"); } catch { /* daftar dimuat ulang di bawah */ }
    refreshList();
  });

  refreshState();
  setInterval(refreshState, 10000);
  setInterval(refreshList, 5000);
})();
```

- [ ] **Step 5: Tambah rute halaman di `routers/qna.py`**

Import: `from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse`. Tambahkan setelah `require_qna_enabled`:
```python
@router.get("/tanya", dependencies=[Depends(require_qna_enabled)])
def jemaat_page():
    return FileResponse("frontend/qna/tanya.html")
```
Resep di `tests/test_no_blocking_io.py`:
```python
    ("GET", "/tanya"): Recipe(),
```

- [ ] **Step 6: Jalankan tes**

Run: `venv/bin/pytest tests/test_qna_frontend.py tests/test_qna_api.py tests/test_no_blocking_io.py -v`
Expected: PASS

- [ ] **Step 7: Cek manual di HP-size**

Jalankan `venv/bin/uvicorn main:app --port 8000`, nyalakan flag `qna` dari dashboard dev, lalu buka `http://localhost:8000/tanya` dengan viewport 375px. Pastikan tidak ada scroll horizontal dan tombol Kirim mudah dijangkau jempol.

- [ ] **Step 8: Commit**

```bash
git add frontend/qna/tanya.html frontend/qna/jemaat.js routers/qna.py tests/test_qna_frontend.py tests/test_qna_api.py tests/test_no_blocking_io.py
git commit -m "feat(qna): halaman jemaat kirim dan dukung pertanyaan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Halaman admin `/tanya/admin`

**Files:**
- Create: `frontend/qna/tanya-admin.html`, `frontend/qna/admin.js`
- Modify: `routers/qna.py`, `tests/test_no_blocking_io.py`
- Test: `tests/test_qna_frontend.py`, `tests/test_qna_api.py`

**Interfaces:**
- Consumes: `QnaApi.admin.*`, `QnaApi.subscribe`, `QNA_CONFIG.pages.display`.
- Produces: `#login`/`#pin`/`#loginMsg`, `#app`, `#conn`, `#session`, `#mode`, `#tts`, `#hide`, `#replay`, `#linkOverlay`, `#linkFull`, `#sort`, kolom `#col-{masuk,disetujui,tampil,selesai,ditolak}`, penghitung `#n-*`, tombol `[data-act][data-id]`, `#toast`.

- [ ] **Step 1: Tulis tes yang gagal**

Di `tests/test_qna_frontend.py`:
```python
def test_admin_moves_question_through_whole_flow(page: Page, backend):
    backend.add("Pertanyaan pertama")
    page.goto(f"{BASE}/tanya/admin")
    page.click("#col-masuk [data-act=approve]")
    expect(page.locator("#col-disetujui .qitem")).to_have_count(1)
    page.click("#col-disetujui [data-act=show]")
    expect(page.locator("#col-tampil .qitem")).to_contain_text("Pertanyaan pertama")
    assert backend.settings["show_nonce"] == 1
    page.click("#col-tampil [data-act=done]")
    expect(page.locator("#col-selesai .qitem")).to_have_count(1)
    expect(page.locator("#n-selesai")).to_have_text("1")


def test_admin_sorts_approved_by_votes_in_upvote_mode(page: Page, backend):
    backend.settings["points_mode"] = "upvote"
    backend.add("Sedikit", "disetujui", votes=1)
    backend.add("Banyak", "disetujui", votes=9)
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#col-disetujui .qitem").first).to_contain_text("Banyak")
    page.select_option("#sort", "time")
    expect(page.locator("#col-disetujui .qitem").first).to_contain_text("Sedikit")


def test_admin_locks_mode_while_session_open(page: Page, backend):
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#mode")).to_be_disabled()
    expect(page.locator("#session")).to_have_text("Tutup sesi")
    page.click("#session")
    expect(page.locator("#session")).to_have_text("Buka sesi")
    expect(page.locator("#mode")).to_be_enabled()
    assert backend.settings["session_open"] is False


def test_admin_screen_buttons(page: Page, backend):
    qid = backend.add("Tampil", "disetujui")
    backend.act(qid, "show")
    page.goto(f"{BASE}/tanya/admin")
    expect(page.locator("#conn")).to_have_class(re.compile(r"\bon\b"))
    with page.expect_response("**/api/qna/admin/screen/hide"):
        page.click("#hide")
    assert backend.settings["hidden"] is True
    with page.expect_response("**/api/qna/admin/screen/replay"):
        page.click("#replay")
    assert backend.settings["hidden"] is False
```

Di `tests/test_qna_api.py`:
```python
def test_admin_page_needs_login():
    res = client.get("/tanya/admin", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/login"
    assert admin_client().get("/tanya/admin").status_code == 200
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_frontend.py -k admin -v`
Expected: FAIL (file tidak ada).

- [ ] **Step 3: Tulis `frontend/qna/tanya-admin.html`**

```html
<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Tanya Jawab · KP GKI Bromo</title>
  <link rel="stylesheet" href="/static/qna/qna.css">
</head>
<body class="admin">
  <form id="login" class="card setup" hidden>
    <h1>Masuk admin</h1>
    <label for="pin">PIN panitia</label>
    <input id="pin" type="password" autocomplete="current-password" required>
    <button class="primary">Masuk</button>
    <p id="loginMsg" class="muted" role="status"></p>
  </form>

  <main id="app" hidden>
    <div class="toolbar">
      <span id="conn" class="conn" title="Status koneksi"></span>
      <button id="session" type="button" class="primary">Buka sesi</button>
      <label>Mode poin
        <select id="mode"><option value="hiasan">Hiasan</option><option value="upvote">Upvote</option></select>
      </label>
      <label>Suara
        <select id="tts"><option value="browser">Browser</option><option value="cloud">Cloud</option></select>
      </label>
      <button id="hide" type="button">Kosongkan layar</button>
      <button id="replay" type="button">Putar ulang</button>
      <a id="linkOverlay" target="_blank" rel="noopener">Display overlay</a>
      <a id="linkFull" target="_blank" rel="noopener">Display penuh</a>
    </div>

    <div class="board">
      <section class="col">
        <h2>Masuk (<span id="n-masuk">0</span>)</h2>
        <ul id="col-masuk" class="qlist"></ul>
      </section>
      <section class="col">
        <h2>Disetujui (<span id="n-disetujui">0</span>)
          <select id="sort" aria-label="Urutkan"><option value="votes">Dukungan</option><option value="time">Waktu</option></select>
        </h2>
        <ul id="col-disetujui" class="qlist"></ul>
      </section>
      <section class="col">
        <h2>Tampil</h2>
        <ul id="col-tampil" class="qlist"></ul>
        <h2>Selesai (<span id="n-selesai">0</span>)</h2>
        <ul id="col-selesai" class="qlist"></ul>
        <h2>Ditolak (<span id="n-ditolak">0</span>)</h2>
        <ul id="col-ditolak" class="qlist"></ul>
      </section>
    </div>
  </main>

  <div id="toast" class="toast" role="alert" hidden></div>

  <script src="/static/qna/config.js"></script>
  <script src="/static/qna/qna-common.js"></script>
  <script src="/static/qna/qna-api-kp.js"></script>
  <script src="/static/qna/qna-api-supabase.js"></script>
  <script src="/static/qna/admin.js"></script>
</body>
</html>
```

- [ ] **Step 4: Tulis `frontend/qna/admin.js`**

```js
(function () {
  const $ = (id) => document.getElementById(id);
  const pages = window.QNA_CONFIG.pages;
  const ACTIONS = {
    masuk: [["approve", "Setujui"], ["reject", "Tolak"]],
    disetujui: [["show", "Tampilkan"], ["reject", "Tolak"]],
    tampil: [["done", "Selesai"]],
    selesai: [["show", "Tampilkan lagi"]],
    ditolak: [["approve", "Setujui"]],
  };
  let data = { settings: {}, questions: [] };
  let loading = false;
  let again = false;
  let started = false;

  function toast(text) {
    const t = $("toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { t.hidden = true; }, 4000);
  }

  function fail(err) {
    if (err.code === "forbidden") {
      if (QnaApi.admin.needsLogin) return showLogin();
      window.location.href = "/login";
      return;
    }
    toast(err.message);
  }

  // Satu pemuatan dalam satu waktu; sinyal yang datang di tengahnya dilipat
  // jadi satu pemuatan susulan, supaya rentetan event tidak membanjiri server.
  async function load() {
    if (loading) { again = true; return; }
    loading = true;
    try {
      data = await QnaApi.admin.list();
      $("conn").classList.add("on");
      render();
    } catch (err) {
      $("conn").classList.remove("on");
      fail(err);
    } finally {
      loading = false;
      if (again) { again = false; load(); }
    }
  }

  function item(q) {
    const votes = data.settings.points_mode === "upvote" ? `<span class="muted">▲ ${q.votes}</span>` : "";
    const buttons = (ACTIONS[q.status] || []).map(([act, label]) =>
      `<button type="button" data-id="${Qna.escapeHtml(q.id)}" data-act="${act}"${act === "show" ? ' class="primary"' : ""}>${label}</button>`,
    ).join("");
    return `<li class="qitem"><p>${Qna.escapeHtml(q.body)}</p><div class="actions">${votes}${buttons}</div></li>`;
  }

  function render() {
    const s = data.settings;
    $("session").textContent = s.session_open ? "Tutup sesi" : "Buka sesi";
    $("session").classList.toggle("primary", !s.session_open);
    $("mode").value = s.points_mode;
    $("mode").disabled = !!s.session_open;
    $("tts").value = s.tts_engine;

    const groups = { masuk: [], disetujui: [], tampil: [], selesai: [], ditolak: [] };
    for (const q of data.questions) (groups[q.status] || []).push(q);
    const oldest = (a, b) => a.created_at.localeCompare(b.created_at);
    groups.masuk.sort(oldest);
    groups.disetujui.sort($("sort").value === "votes" ? (a, b) => b.votes - a.votes || oldest(a, b) : oldest);
    groups.selesai.sort((a, b) => (b.shown_at || "").localeCompare(a.shown_at || ""));
    for (const [status, list] of Object.entries(groups)) {
      $(`col-${status}`).innerHTML = list.map(item).join("");
      const counter = $(`n-${status}`);
      if (counter) counter.textContent = list.length;
    }
  }

  async function run(promise) {
    try { await promise; } catch (err) { fail(err); }
    load();
  }

  document.body.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    btn.disabled = true;
    run(QnaApi.admin.act(btn.dataset.id, btn.dataset.act));
  });
  $("session").onclick = () => run(QnaApi.admin.settings({ session_open: !data.settings.session_open }));
  $("mode").onchange = () => run(QnaApi.admin.settings({ points_mode: $("mode").value }));
  $("tts").onchange = () => run(QnaApi.admin.settings({ tts_engine: $("tts").value }));
  $("sort").onchange = render;
  $("hide").onclick = () => run(QnaApi.admin.screen("hide"));
  $("replay").onclick = () => run(QnaApi.admin.screen("replay"));
  $("linkOverlay").href = `${pages.display}?mode=overlay`;
  $("linkFull").href = `${pages.display}?mode=full`;

  function showLogin() {
    $("app").hidden = true;
    $("login").hidden = false;
    $("pin").focus();
  }

  function start() {
    $("login").hidden = true;
    $("app").hidden = false;
    if (started) return load();
    started = true;
    QnaApi.subscribe(() => load(), (on) => $("conn").classList.toggle("on", on));
  }

  $("login").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await QnaApi.admin.login($("pin").value);
      $("pin").value = "";
      start();
    } catch (err) {
      $("loginMsg").textContent = err.code === "forbidden" ? "PIN salah." : err.message;
    }
  });

  if (QnaApi.admin.needsLogin && !QnaApi.admin.hasPin()) showLogin();
  else start();
})();
```

- [ ] **Step 5: Rute halaman di `routers/qna.py`**

```python
@router.get("/tanya/admin", dependencies=[Depends(check_admin_auth)])
def admin_page():
    return FileResponse("frontend/qna/tanya-admin.html")
```
Resep: `("GET", "/tanya/admin"): Recipe(admin=True),`

- [ ] **Step 6: Jalankan tes**

Run: `venv/bin/pytest tests/test_qna_frontend.py tests/test_qna_api.py tests/test_no_blocking_io.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/qna/tanya-admin.html frontend/qna/admin.js routers/qna.py tests/test_qna_frontend.py tests/test_qna_api.py tests/test_no_blocking_io.py
git commit -m "feat(qna): halaman admin antrean dan kontrol layar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Display videotron `/tanya/display`

**Files:**
- Create: `frontend/qna/tanya-display.html`, `frontend/qna/display.js`
- Modify: `routers/qna.py`, `tests/test_no_blocking_io.py`, `tests/test_qna_api.py`
- Test: `tests/test_qna_frontend.py`

**Interfaces:**
- Consumes: `QnaApi.display`, `QnaApi.tts`, `QnaApi.subscribe`.
- Produces: `#setup`, `#voice`, `#test`, `#start`, `#modeLabel`, `#stage`, `#alert`, `#points`, `#qbody`, `#conn`; kelas body `mode-overlay`/`mode-full`; `localStorage["qna_voice"]`.

- [ ] **Step 1: Tulis tes yang gagal**

Di `tests/test_qna_api.py`:
```python
def test_display_page_needs_login():
    res = client.get("/tanya/display", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/login"
    assert admin_client().get("/tanya/display").status_code == 200
```

Di `tests/test_qna_frontend.py`:
```python
def test_display_announces_shown_question_and_hides(page: Page, backend):
    qid = backend.add("Apa rasanya jadi pemuda di gereja?", "disetujui")
    page.goto(f"{BASE}/tanya/display?mode=overlay")
    expect(page.locator("body")).to_have_class(re.compile(r"\bmode-overlay\b"))
    page.click("#start")
    expect(page.locator("#setup")).to_be_hidden()
    expect(page.locator("#alert")).to_be_hidden()
    backend.act(qid, "show")
    # Bunyi notifikasi 1,2 detik + jeda polling/SSE.
    expect(page.locator("#qbody")).to_have_text("Apa rasanya jadi pemuda di gereja?", timeout=10000)
    expect(page.locator("#points")).to_have_text("Seseorang memberikan 50 poin!")
    backend.screen("hide")
    expect(page.locator("#alert")).to_be_hidden(timeout=10000)


def test_display_shows_current_question_silently_on_load(page: Page, backend):
    qid = backend.add("Sudah tampil sebelum laptop dinyalakan", "disetujui")
    backend.act(qid, "show")
    page.goto(f"{BASE}/tanya/display")
    expect(page.locator("body")).to_have_class(re.compile(r"\bmode-full\b"))
    page.click("#start")
    expect(page.locator("#qbody")).to_have_text("Sudah tampil sebelum laptop dinyalakan", timeout=5000)
```

- [ ] **Step 2: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_frontend.py tests/test_qna_api.py -k display -v`
Expected: FAIL

- [ ] **Step 3: Tulis `frontend/qna/tanya-display.html`**

```html
<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Layar Tanya Jawab · KP GKI Bromo</title>
  <link rel="stylesheet" href="/static/qna/qna.css">
</head>
<body class="display">
  <section id="setup" class="card setup">
    <h1>Layar tanya jawab</h1>
    <p class="muted">Mode: <b id="modeLabel"></b>. Tambahkan <code>?mode=overlay</code> di URL untuk Browser Source OBS.</p>
    <label for="voice">Suara browser</label>
    <select id="voice"></select>
    <button id="test" type="button">Uji suara</button>
    <button id="start" type="button" class="primary">Aktifkan suara &amp; mulai</button>
  </section>

  <div id="stage" class="stage" hidden>
    <article id="alert" class="alert" hidden aria-live="polite">
      <p id="points" class="points"></p>
      <p id="qbody" class="qbody"></p>
    </article>
  </div>
  <span id="conn" class="conn" title="Status koneksi"></span>

  <script src="/static/qna/config.js"></script>
  <script src="/static/qna/qna-common.js"></script>
  <script src="/static/qna/qna-api-kp.js"></script>
  <script src="/static/qna/qna-api-supabase.js"></script>
  <script src="/static/qna/display.js"></script>
</body>
</html>
```

- [ ] **Step 4: Tulis `frontend/qna/display.js`**

```js
(function () {
  const $ = (id) => document.getElementById(id);
  const mode = new URLSearchParams(location.search).get("mode") === "overlay" ? "overlay" : "full";
  document.body.classList.add(`mode-${mode}`);
  $("modeLabel").textContent = mode === "overlay" ? "overlay (transparan, untuk OBS)" : "layar penuh";

  const VOICE_KEY = "qna_voice";
  const CLOUD_TIMEOUT_MS = 4500;
  let audioCtx = null;
  let lastNonce = null;
  let seq = 0;

  // Daftar suara berbeda di tiap laptop, jadi pilihannya disimpan di laptop ini.
  function fillVoices() {
    const list = speechSynthesis.getVoices().slice().sort((a, b) =>
      (b.lang.startsWith("id") - a.lang.startsWith("id")) || a.name.localeCompare(b.name));
    let saved = null;
    try { saved = localStorage.getItem(VOICE_KEY); } catch { /* tanpa penyimpanan */ }
    $("voice").innerHTML = list.map((v) =>
      `<option value="${Qna.escapeHtml(v.name)}">${Qna.escapeHtml(v.name)} (${Qna.escapeHtml(v.lang)})</option>`).join("");
    if (saved && list.some((v) => v.name === saved)) $("voice").value = saved;
  }
  fillVoices();
  speechSynthesis.onvoiceschanged = fillVoices;
  $("voice").onchange = () => {
    try { localStorage.setItem(VOICE_KEY, $("voice").value); } catch { /* tanpa penyimpanan */ }
  };

  function speakBrowser(text) {
    return new Promise((resolve) => {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "id-ID";
      const voice = speechSynthesis.getVoices().find((v) => v.name === $("voice").value);
      if (voice) u.voice = voice;
      u.onend = () => resolve();
      u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }

  function withTimeout(promise, ms) {
    return Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms))]);
  }

  async function speak(text, engine) {
    if (engine === "cloud") {
      try {
        const blob = await withTimeout(QnaApi.tts(text), CLOUD_TIMEOUT_MS);
        if (blob) {
          const audio = new Audio(URL.createObjectURL(blob));
          await new Promise((resolve, reject) => {
            audio.onended = resolve;
            audio.onerror = reject;
            audio.play().catch(reject);
          });
          return;
        }
      } catch { /* jatuh ke suara browser */ }
    }
    await speakBrowser(text);
  }

  // Tiga nada naik ala notifikasi donasi, dibangkitkan langsung tanpa file audio.
  function chime() {
    const now = audioCtx.currentTime;
    [[880, 0], [1318.5, 0.18], [1760, 0.36]].forEach(([freq, at]) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "triangle";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + at);
      gain.gain.exponentialRampToValueAtTime(0.4, now + at + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + at + 0.8);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + at);
      osc.stop(now + at + 0.85);
    });
    return new Promise((resolve) => setTimeout(resolve, 1200));
  }

  function showCard(q) {
    $("points").textContent = q.points_text;
    $("qbody").textContent = q.body;
    const card = $("alert");
    card.hidden = true;
    void card.offsetWidth; // ulang animasi masuk
    card.hidden = false;
  }

  async function present(d, announce) {
    const mine = ++seq;
    speechSynthesis.cancel();
    if (!d.question) { $("alert").hidden = true; return; }
    if (announce) {
      $("alert").hidden = true;
      await chime();
      if (mine !== seq) return; // admin sudah menekan aksi lain saat bunyi berjalan
    }
    showCard(d.question);
    if (announce) await speak(`${d.question.points_text} ${d.question.body}`, d.tts_engine);
  }

  function setConn(on) { $("conn").classList.toggle("on", on); }

  async function sync() {
    let d;
    try {
      d = await QnaApi.display();
      setConn(true);
    } catch {
      setConn(false);
      return;
    }
    if (lastNonce === null) {
      // Pertama kali: tampilkan apa adanya tanpa bunyi, supaya laptop yang
      // dimuat ulang di tengah acara tidak mengulang alert.
      lastNonce = d.nonce;
      present(d, false);
      return;
    }
    if (d.nonce === lastNonce) return;
    lastNonce = d.nonce;
    present(d, true);
  }

  $("test").onclick = () => speakBrowser("Seseorang memberikan 10 poin! Ini contoh suara untuk uji coba.");

  // Chrome memblokir audio sampai ada interaksi; tombol ini membukanya sekali.
  $("start").onclick = async () => {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    await audioCtx.resume();
    $("setup").hidden = true;
    $("stage").hidden = false;
    QnaApi.subscribe((kind) => { if (kind !== "questions" && kind !== "settings") sync(); }, setConn);
  };
})();
```

- [ ] **Step 5: Rute + resep**

```python
@router.get("/tanya/display", dependencies=[Depends(check_admin_auth)])
def display_page():
    return FileResponse("frontend/qna/tanya-display.html")
```
Resep: `("GET", "/tanya/display"): Recipe(admin=True),`

- [ ] **Step 6: Jalankan seluruh suite + lint**

Run: `venv/bin/pytest tests/ --ignore=tests/test_e2e_playwright.py -q && venv/bin/ruff check .`
Expected: PASS, ruff bersih.

- [ ] **Step 7: Cek manual dengan suara**

Jalankan server lokal, login, buka `/tanya/display?mode=full` di Chrome. Pilih "Google Bahasa Indonesia", klik Uji suara (harus terdengar), lalu Aktifkan. Dari tab admin, setujui + tampilkan satu pertanyaan: notifikasi berbunyi → kartu muncul → suara membaca. Ulangi dengan mode suara **Cloud** (kalau `GOOGLE_TTS_API_KEY` diisi), lalu kosongkan key dan pastikan suara browser tetap berbunyi.

- [ ] **Step 8: Commit**

```bash
git add frontend/qna/tanya-display.html frontend/qna/display.js routers/qna.py tests/test_qna_frontend.py tests/test_qna_api.py tests/test_no_blocking_io.py
git commit -m "feat(qna): display videotron dengan bunyi notifikasi dan suara AI

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Jalur cadangan statis

**Files:**
- Create: `scripts/build_qna_standalone.sh`
- Test: `tests/test_qna_frontend.py` (adapter Supabase), `tests/test_qna_standalone_build.py`

**Interfaces:**
- Consumes: semua file `frontend/qna/*`; fungsi SQL Task 1.
- Produces: folder `<out>/index.html`, `<out>/admin.html`, `<out>/display.html`, `<out>/static/qna/*`, `<out>/_headers`, dengan `config.js` ber-`backend: "supabase"`.

- [ ] **Step 1: Tulis tes adapter Supabase yang gagal** (di `tests/test_qna_frontend.py`)

```python
SB = "https://sb.test"
FALLBACK_CONFIG = f"""window.QNA_CONFIG = {{
  backend: "supabase", supabaseUrl: "{SB}", supabaseKey: "sb_publishable_uji",
  pages: {{ jemaat: "/", admin: "/admin.html", display: "/display.html" }},
}};"""


@pytest.fixture
def fallback(page: Page):
    """Halaman yang sama, tapi config.js menunjuk adapter Supabase."""
    calls = []
    state = {"session_open": True, "points_mode": "hiasan", "tts_engine": "browser", "hidden": False, "show_nonce": 0}
    questions = []

    def site(route: Route):
        path = urlsplit(route.request.url).path
        if path == "/static/qna/config.js":
            route.fulfill(content_type="application/javascript", body=FALLBACK_CONFIG)
        elif not serve_static(route, {"/": "/tanya", "/admin.html": "/tanya/admin"}.get(path, path)):
            route.fulfill(status=404, body="")

    def rpc(route: Route):
        fn = urlsplit(route.request.url).path.rsplit("/", 1)[-1]
        args = json.loads(route.request.post_data or "{}")
        calls.append((fn, args, route.request.headers.get("apikey")))
        if fn.startswith("qna_admin") and args.get("p_pin") != "pin-uji-panjang":
            return route.fulfill(status=400, content_type="application/json",
                                 body=json.dumps({"code": "P0001", "message": "forbidden"}))
        if fn == "qna_state":
            body = {k: state[k] for k in ("session_open", "points_mode")}
        elif fn == "qna_submit":
            if any(a.get("p_device") == args["p_device"] for f, a, _ in calls[:-1] if f == "qna_submit"):
                return route.fulfill(status=400, content_type="application/json",
                                     body=json.dumps({"code": "P0001", "message": "cooldown:17"}))
            questions.append(args["p_body"])
            body = {"id": "00000000-0000-4000-8000-000000000001"}
        elif fn == "qna_admin_list":
            body = {"settings": state, "questions": [
                {"id": "00000000-0000-4000-8000-000000000001", "body": b, "status": "masuk",
                 "created_at": "2026-11-14T10:00:00+00:00", "shown_at": None, "votes": 0} for b in questions]}
        else:
            body = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    page.route(f"{BASE}/**", site)
    page.route(f"{SB}/rest/v1/rpc/**", rpc)
    return calls


def test_fallback_jemaat_submits_via_rpc_and_maps_cooldown(page: Page, fallback):
    page.goto(f"{BASE}/")
    page.fill("#body", "Pertanyaan lewat jalur cadangan")
    page.click("#send")
    expect(page.locator("#msg")).to_contain_text("Terkirim")
    fn, args, apikey = next(c for c in fallback if c[0] == "qna_submit")
    assert args["p_body"] == "Pertanyaan lewat jalur cadangan"
    assert apikey == "sb_publishable_uji"
    page.reload()  # device_id tetap sama (localStorage), jadi jeda harus terpicu
    page.fill("#body", "Kedua kalinya")
    page.click("#send")
    expect(page.locator("#send")).to_contain_text("Tunggu")


def test_fallback_admin_requires_pin(page: Page, fallback):
    page.goto(f"{BASE}/admin.html")
    expect(page.locator("#login")).to_be_visible()
    page.fill("#pin", "salah")
    page.click("#login button")
    expect(page.locator("#loginMsg")).to_have_text("PIN salah.")
    page.fill("#pin", "pin-uji-panjang")
    page.click("#login button")
    expect(page.locator("#app")).to_be_visible()
    expect(page.locator("#linkOverlay")).to_have_attribute("href", "/display.html?mode=overlay")
```
- [ ] **Step 2: Jalankan tes adapter**

Run: `venv/bin/pytest tests/test_qna_frontend.py -k fallback -v`
Expected: PASS (adapter sudah ditulis di Task 7). Kalau gagal, perbaiki adapter, bukan tesnya.

- [ ] **Step 3: Tulis tes build yang gagal (`tests/test_qna_standalone_build.py`)**

```python
import subprocess  # noqa: S404 — menjalankan skrip build milik repo sendiri
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_qna_standalone.sh"


def run(*args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False)  # noqa: S603


def test_build_produces_static_site_pointing_to_supabase(tmp_path):
    out = tmp_path / "situs"
    res = run(str(out), "https://abc.supabase.co", "sb_publishable_xyz")
    assert res.returncode == 0, res.stderr
    for name in ("index.html", "admin.html", "display.html", "_headers",
                 "static/qna/qna-api-supabase.js", "static/qna/qna.css"):
        assert (out / name).exists(), name
    config = (out / "static/qna/config.js").read_text()
    assert 'backend: "supabase"' in config
    assert "https://abc.supabase.co" in config and "sb_publishable_xyz" in config
    assert '"/admin.html"' in config


def test_build_refuses_secret_key(tmp_path):
    res = run(str(tmp_path / "situs"), "https://abc.supabase.co", "sb_secret_bocor")
    assert res.returncode != 0
    assert not (tmp_path / "situs").exists()


def test_build_refuses_to_wipe_unrelated_folder(tmp_path):
    (tmp_path / "penting.txt").write_text("jangan dihapus")
    res = run(str(tmp_path), "https://abc.supabase.co", "sb_publishable_xyz")
    assert res.returncode != 0
    assert (tmp_path / "penting.txt").exists()
```

- [ ] **Step 4: Jalankan untuk melihat gagal**

Run: `venv/bin/pytest tests/test_qna_standalone_build.py -v`
Expected: FAIL (skrip tidak ada).

- [ ] **Step 5: Tulis `scripts/build_qna_standalone.sh`**

```bash
#!/usr/bin/env bash
# Bangun situs statis jalur cadangan tanya jawab (spec §13).
# Halaman sama persis dengan web KP; hanya config.js yang menunjuk adapter Supabase.
#
# Pakai: scripts/build_qna_standalone.sh <folder-keluaran> <SUPABASE_URL> <PUBLISHABLE_KEY>
# Lalu seret folder keluaran ke https://app.netlify.com/drop.
# Situsnya baru berfungsi setelah scripts/qna_fallback_on.sql dijalankan.
set -euo pipefail

OUT="${1:?folder keluaran}"
URL="${2:?SUPABASE_URL}"
KEY="${3:?publishable key}"

case "$KEY" in
  sb_secret_*) echo "Itu secret key. Pakai publishable key (sb_publishable_...)." >&2; exit 1 ;;
esac

# rm -rf hanya untuk folder kosong atau hasil build sebelumnya.
if [ -e "$OUT" ] && [ -n "$(ls -A "$OUT")" ] && [ ! -f "$OUT/static/qna/qna-api-supabase.js" ]; then
  echo "Folder $OUT berisi file lain; pilih folder kosong." >&2
  exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)/frontend/qna"
rm -rf "$OUT"
mkdir -p "$OUT/static/qna"
cp "$SRC"/*.js "$SRC"/*.css "$OUT/static/qna/"
cp "$SRC/tanya.html" "$OUT/index.html"
cp "$SRC/tanya-admin.html" "$OUT/admin.html"
cp "$SRC/tanya-display.html" "$OUT/display.html"

cat > "$OUT/static/qna/config.js" <<EOF
// Dibangkitkan oleh scripts/build_qna_standalone.sh — jalur cadangan tanpa web KP.
window.QNA_CONFIG = {
  backend: "supabase",
  supabaseUrl: "$URL",
  supabaseKey: "$KEY",
  pages: { jemaat: "/", admin: "/admin.html", display: "/display.html" },
};
EOF

# Sama dengan web KP: browser wajib memvalidasi ulang, jangan pakai JS lama.
cat > "$OUT/_headers" <<'EOF'
/*
  Cache-Control: no-cache, must-revalidate
EOF

echo "Siap: $OUT — unggah ke https://app.netlify.com/drop"
```
Lalu `chmod +x scripts/build_qna_standalone.sh`.

- [ ] **Step 6: Jalankan tes**

Run: `venv/bin/pytest tests/test_qna_standalone_build.py tests/test_qna_frontend.py -v && venv/bin/ruff check .`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/build_qna_standalone.sh tests/test_qna_standalone_build.py tests/test_qna_frontend.py
git commit -m "feat(qna): build situs statis jalur cadangan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Uji beban + runbook hari H

**Files:**
- Create: `scripts/qna_loadtest.py`
- Create: `/Users/josetaneo/GKI BROMO/KP/PODCAST 14 NOV 26/docs/runbook-hari-h.md`

**Interfaces:**
- Consumes: API publik Task 4.

- [ ] **Step 1: Tulis `scripts/qna_loadtest.py`**

```python
"""Uji beban tanya jawab: N HP mengirim satu pertanyaan lalu polling daftar.

Pakai (saat gladi, flag qna MENYALA, sesi DIBUKA, mode upvote):
    venv/bin/python scripts/qna_loadtest.py https://<domain-web-kp> --devices 130 --minutes 5
Kiriman disebar dalam 3 menit (< 60/menit, batas per IP), karena skrip ini
berjalan dari satu IP, sama seperti satu WiFi gereja.

Bersihkan sesudahnya di SQL Editor:
    delete from qna_questions where body like '[LOADTEST]%';
Keluar dengan kode 1 kalau p95 > 500 ms atau ada error.
"""
import argparse
import asyncio
import random
import statistics
import time
import uuid

import httpx

SUBMIT_SPREAD_S = 180


async def device(client, base, deadline, latencies, errors):
    dev = str(uuid.uuid4())
    await asyncio.sleep(random.uniform(0, SUBMIT_SPREAD_S))  # noqa: S311 — jitter beban, bukan kriptografi
    started = time.perf_counter()
    try:
        res = await client.post(f"{base}/api/qna/questions",
                                json={"body": f"[LOADTEST] pertanyaan {dev[:8]}", "device_id": dev})
        if res.status_code != 200:
            errors.append(("submit", res.status_code))
    except httpx.HTTPError as e:
        errors.append(("submit", type(e).__name__))
    latencies.append(time.perf_counter() - started)
    while time.monotonic() < deadline:
        started = time.perf_counter()
        try:
            res = await client.get(f"{base}/api/qna/questions/public", params={"device_id": dev})
            if res.status_code != 200:
                errors.append(("list", res.status_code))
        except httpx.HTTPError as e:
            errors.append(("list", type(e).__name__))
        latencies.append(time.perf_counter() - started)
        await asyncio.sleep(5 + random.uniform(-0.5, 0.5))  # noqa: S311 — jitter beban


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--devices", type=int, default=130)
    parser.add_argument("--minutes", type=float, default=5)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    deadline = time.monotonic() + args.minutes * 60
    latencies, errors = [], []
    limits = httpx.Limits(max_connections=args.devices)
    async with httpx.AsyncClient(timeout=10, limits=limits) as client:
        await asyncio.gather(*(device(client, base, deadline, latencies, errors) for _ in range(args.devices)))
    p50 = statistics.median(latencies) * 1000
    p95 = statistics.quantiles(latencies, n=20)[18] * 1000
    print(f"request: {len(latencies)}  p50: {p50:.0f} ms  p95: {p95:.0f} ms  error: {len(errors)}")
    if errors:
        print("contoh error:", errors[:10])
    raise SystemExit(1 if errors or p95 > 500 else 0)


if __name__ == "__main__":
    asyncio.run(main())
```

Run: `venv/bin/ruff check scripts/qna_loadtest.py`
Expected: bersih.

- [ ] **Step 2: Tulis runbook `PODCAST 14 NOV 26/docs/runbook-hari-h.md`**

```markdown
# Runbook Tanya Jawab Live Podcast — Sabtu 14 Nov 2026

## Peran
- **Admin (Sie Multimedia):** laptop/tablet admin, memilih dan menampilkan pertanyaan.
- **Operator videotron:** laptop display (Chrome), OBS kalau mode overlay.
- **Pemegang PIN cadangan:** 2 orang panitia.

## Gladi bersih (paling lambat Kamis 12 Nov)
1. Deploy branch `feat/qna-podcast` ke VPS. Pastikan migrasi `2026-11-04_qna.sql` sudah jalan dan `qna_selftest.sql` lulus.
2. Isi `GOOGLE_TTS_API_KEY` di `.env` VPS (opsional), lalu restart layanan.
3. Jalankan `qna_set_pin.sql` dengan frasa minimal 12 karakter. Simpan frasanya di 2 orang.
4. Build & deploy situs cadangan:
   `scripts/build_qna_standalone.sh ~/qna-cadangan <SUPABASE_URL> <sb_publishable_...>` → seret ke Netlify Drop → catat URL-nya.
5. Siapkan **dua QR**: utama `https://<web-kp>/tanya` dan cadangan `https://<netlify>/`.
6. Uji beban: nyalakan flag `qna`, buka sesi, mode upvote, jalankan `scripts/qna_loadtest.py https://<web-kp>` sambil kiosk absen diuji. Target: keluar 0 (p95 < 500 ms). Setelah itu jalankan `delete from qna_questions where body like '[LOADTEST]%';`.
7. Di ruangan, dengan laptop + videotron asli:
   - Login web KP di laptop display → `/tanya/display?mode=full` (atau `overlay` sebagai Browser Source OBS, centang "Control audio via OBS" kalau suara lewat mixer).
   - Pilih suara, klik **Uji suara**, atur volume ruangan.
   - Scan QR dari 3 HP (kuota + WiFi gereja), kirim, setujui, tampilkan, kosongkan, putar ulang.
8. **Latihan pindah ke cadangan** (lihat bawah), lalu `qna_fallback_off.sql`.
9. Tutup sesi, hapus data latihan: `delete from qna_questions;`, matikan flag `qna`.

## Hari H
1. 16.00: nyalakan flag `qna` (sesi masih **tutup**), pilih mode poin.
2. Laptop display: login → buka display → **Aktifkan suara & mulai**. Titik di pojok harus hijau.
3. Admin: buka `/tanya/admin`, titik koneksi hijau.
4. Saat sesi tanya jawab dimulai: **Buka sesi**, lalu tampilkan QR utama.
5. Alur: Masuk → **Setujui** → **Tampilkan** → (narasumber menjawab) → **Selesai**.
6. Selesai acara: **Tutup sesi**, lalu matikan flag `qna`.

## Pindah ke jalur cadangan (kalau web KP tidak bisa dibuka > 2 menit)
1. Supabase SQL Editor → jalankan `scripts/qna_fallback_on.sql`.
2. Admin buka `https://<netlify>/admin.html`, lalu masukkan PIN.
3. Laptop display buka `https://<netlify>/display.html?mode=full` → Aktifkan suara.
4. Tampilkan **QR cadangan**. Pertanyaan yang sudah masuk tetap ada (database sama).
5. Catatan: suara selalu memakai suara browser, dan jeda tampil bisa sampai sekitar 2 detik.
6. Setelah acara: jalankan `scripts/qna_fallback_off.sql`.

## Kalau Supabase juga mati
Kedua jalur ikut mati. Rencana terakhirnya, MC meminta pertanyaan lewat kertas atau Google Form cadangan, lalu membacakannya langsung.
```

- [ ] **Step 3: Commit (repo FaceID-KP)**

```bash
git add scripts/qna_loadtest.py
git commit -m "chore(qna): skrip uji beban tanya jawab

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Verifikasi akhir & PR

- [ ] **Step 1: Suite lengkap + lint**

Run: `venv/bin/pytest tests/ --ignore=tests/test_e2e_playwright.py -q && venv/bin/ruff check .`
Expected: semua PASS, ruff bersih.

- [ ] **Step 2: Uji ujung-ke-ujung lokal dengan DB sungguhan**

`venv/bin/uvicorn main:app --port 8000`, lalu:
- nyalakan flag `qna`;
- tiga tab: `/tanya`, `/tanya/admin`, `/tanya/display`;
- kirim → setujui → tampilkan: alert muncul di display dalam waktu kurang dari 2 detik;
- coba mode upvote dari 2 profil browser.

Bersihkan data uji: `delete from qna_questions;`.

- [ ] **Step 3: Push & PR (minta izin user dulu)**

```bash
git push -u origin feat/qna-podcast
gh pr create --title "feat(qna): tanya jawab live podcast 14 Nov" --body "Modul tanya jawab anonim ala Saweria + jalur cadangan statis. Spec dan runbook ada di folder PODCAST 14 NOV 26.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```
