-- PERBAIKAN: server tidak bisa membaca feature_flags.
--
-- Aplikasi di VPS memakai kunci anon. Dengan RLS aktif tanpa policy, PostgREST
-- mengembalikan NOL BARIS — bukan error. Akibatnya core/flags.py menganggap
-- tabelnya kosong dan memakai nilai bawaan, sehingga saklar yang digeser
-- pengurus di dashboard tidak berpengaruh apa-apa di kiosk. Gejalanya diam:
-- semua terlihat normal, tapi geofence menyala padahal tabel bilang mati.
--
-- scripts/2026-09-17_lark_directory.sql sudah menulis policy baca eksplisit;
-- untuk feature_flags langkah itu terlewat. Ini menutupnya.
--
-- Soal keamanan: membuka tabel ini untuk anon setara dengan tabel `users` yang
-- memang sudah begitu — kunci anon hanya dipakai server, tidak pernah dikirim
-- ke peramban jemaat. Penjagaan siapa boleh menggeser saklar ada di lapisan
-- aplikasi (check_admin_auth di routers/flags.py), bukan di lapisan baris.

alter table feature_flags enable row level security;

drop policy if exists feature_flags_read on feature_flags;
create policy feature_flags_read
  on feature_flags for select
  using (true);

drop policy if exists feature_flags_write on feature_flags;
create policy feature_flags_write
  on feature_flags for all
  using (true)
  with check (true);
