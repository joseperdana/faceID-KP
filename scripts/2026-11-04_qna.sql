-- Modul tanya jawab live podcast (spec: PODCAST 14 NOV 26/docs/superpowers/specs/
-- 2026-11-03-podcast-qna-design.md). Dijalankan lewat Supabase SQL Editor. Aman diulang — tapi menjalankannya ulang menutup kembali jalur cadangan (anon dicabut).
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
  -- Dua ketukan cepat dari HP yang sama tidak boleh lolos jeda bersamaan.
  perform pg_advisory_xact_lock(hashtextextended(p_device::text, 0));
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
  -- Dua admin menekan tombol bersamaan: antre di baris pengaturan supaya
  -- indeks "satu tampil" tidak berujung error 23505 mentah.
  perform 1 from qna_settings where id = 1 for update;
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
  -- Dua admin menekan tombol bersamaan: antre di baris pengaturan supaya
  -- indeks "satu tampil" tidak berujung error 23505 mentah.
  perform 1 from qna_settings where id = 1 for update;
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
