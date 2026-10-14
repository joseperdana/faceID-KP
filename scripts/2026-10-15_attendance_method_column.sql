-- Kolom attendance_logs.method: 'face' | 'manual' | 'registration'.
-- Menggantikan scripts/2026-09-27_attendance_method_registration.sql, yang
-- mengira kolomnya sudah ada.
--
-- Temuan 15 Oktober 2026 lewat Supabase connector: kolom `method` TIDAK PERNAH
-- ada di produksi. Setiap check-in mengirim method, PostgREST menolak dengan
-- PGRST204, lalu DBService.insert_log jatuh ke kolom inti dan melapor ke
-- Sentry. Artinya pemisahan face vs manual — syarat audit di CLAUDE.md —
-- tidak pernah tersimpan sejak awal. Setelah skrip ini, kode yang sedang
-- berjalan di VPS pun langsung menyimpannya, tanpa perlu deploy.
--
-- Baris lama: 'Hadir (Baru)' hanya ditulis oleh /api/register, jadi aman
-- ditandai 'registration'. Baris 'Hadir' lama dibiarkan NULL: tidak ada cara
-- jujur untuk tahu apakah dulu lewat wajah atau manual.
--
-- Aman diulang.

alter table attendance_logs add column if not exists method text;

alter table attendance_logs drop constraint if exists attendance_logs_method_check;
alter table attendance_logs
  add constraint attendance_logs_method_check
  check (method is null or method in ('face', 'manual', 'registration'));

update attendance_logs
set method = 'registration'
where method is null and status = 'Hadir (Baru)';
