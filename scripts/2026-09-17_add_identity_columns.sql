-- Penautan portal <-> Lark Base: kunci gabung + penanda kelengkapan profil.
-- Dijalankan lewat Supabase SQL Editor. Aman diulang (idempoten).
--
-- Catatan penting: phone_e164 SENGAJA tidak unique. Audit 17 Sep 2026 menemukan
-- 5 grup nomor yang dipakai lebih dari satu orang di portal (satu nomor dipakai
-- 3 orang) — kakak-adik atau nomor pinjaman saat mendaftar. Unique constraint
-- akan menolak registrasi mereka di counter.

alter table users add column if not exists phone_e164  text;
alter table users add column if not exists name_key    text;
alter table users add column if not exists lark_status text;

comment on column users.phone_e164  is 'Nomor kanonik +628xxx. Kunci pencocokan dengan Lark Base — bukan penjamin keunikan.';
comment on column users.name_key    is 'Nama ternormalisasi (huruf kecil, tanpa tanda baca) untuk deteksi duplikat saat registrasi.';
comment on column users.lark_status is 'linked | pending | not_found — apakah orang ini sudah punya profil lengkap di Lark Base.';

create index if not exists idx_users_phone_e164 on users (phone_e164);
create index if not exists idx_users_name_key   on users (name_key);

alter table users
  drop constraint if exists users_lark_status_check;
alter table users
  add constraint users_lark_status_check
  check (lark_status is null or lark_status in ('linked', 'pending', 'not_found'));
