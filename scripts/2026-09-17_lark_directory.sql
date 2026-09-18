-- Cermin baca-saja dari Lark Base: dipakai untuk mengenali orang yang PROFILNYA
-- sudah lengkap di Lark tapi wajahnya belum terdaftar di portal (kasus C).
--
-- Kenapa tabel terpisah, bukan diimpor ke users:
-- 168 orang ini tidak punya face_embedding. Kalau barisnya masuk ke users,
-- pencocokan wajah tidak akan menemukan mereka saat datang, tapi pencocokan
-- nama akan — dan registrasi mereka ditolak "sudah terdaftar" tepat di depan
-- orangnya. Tabel referensi terpisah menghindari itu sepenuhnya.
--
-- Isinya bukan sumber kebenaran dan tidak pernah ditulis oleh aplikasi.
-- Disegarkan lewat scripts/seed_lark_directory.py.

create table if not exists lark_directory (
  phone_e164 text primary key,
  full_name  text not null,
  synced_at  timestamptz not null default now()
);

comment on table lark_directory is
  'Cermin baca-saja nomor HP yang sudah terdaftar di Lark Base. Bukan sumber kebenaran; disegarkan manual dari Lark.';

alter table lark_directory enable row level security;

-- Aplikasi hanya perlu membaca. Tidak ada policy tulis: penyegaran dilakukan
-- lewat service key dari script, bukan oleh proses yang melayani kiosk.
drop policy if exists lark_directory_read on lark_directory;
create policy lark_directory_read on lark_directory for select using (true);
