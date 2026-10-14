-- Nilai ketiga untuk attendance_logs.method: 'registration'.
--
-- Kehadiran dari pendaftaran anggota baru dulu disimpan tanpa `method` sama
-- sekali, sehingga tidak bisa dihitung sebagai 'face' maupun 'manual' dan
-- melanggar aturan audit di CLAUDE.md. Aplikasi kini mengirim 'registration'.
--
-- Kalau kolom ini punya CHECK constraint yang hanya mengizinkan 'face' dan
-- 'manual', insert dengan 'registration' akan ditolak. Absensi tetap tersimpan
-- (DBService.insert_log jatuh ke kolom inti dan melapor ke Sentry), tapi nilai
-- method-nya hilang. Skrip ini melebarkan constraint itu kalau ada, dan tidak
-- melakukan apa-apa kalau tidak ada.
--
-- Periksa dulu (boleh dijalankan kapan saja, hanya membaca):
--   select conname, pg_get_constraintdef(oid)
--   from pg_constraint
--   where conrelid = 'attendance_logs'::regclass and contype = 'c';

do $$
declare
  c record;
  found boolean := false;
begin
  for c in
    select conname
    from pg_constraint
    where conrelid = 'attendance_logs'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%method%'
  loop
    execute format('alter table attendance_logs drop constraint %I', c.conname);
    found := true;
  end loop;

  if found then
    alter table attendance_logs
      add constraint attendance_logs_method_check
      check (method is null or method in ('face', 'manual', 'registration'));
  end if;
end $$;

-- Opsional: tandai baris lama dari pendaftaran yang belum punya method.
-- Aman karena status 'Hadir (Baru)' hanya ditulis oleh /api/register.
-- update attendance_logs set method = 'registration'
-- where method is null and status = 'Hadir (Baru)';
