-- Kunci semua tabel dari kunci anon/publishable.
--
-- JANGAN dijalankan sebelum server memakai secret key (sb_secret_...). Selama
-- server masih memakai kunci anon, skrip ini membuat semua query server
-- mengembalikan nol baris — kiosk dan dashboard langsung lumpuh. Cek dulu di
-- log Supabase (edge_logs) bahwa request dari VPS tidak lagi ber-role anon.
--
-- Latar belakang (pemeriksaan lewat Supabase connector, 15 Oktober 2026):
-- - RLS MATI di `users` dan `attendance_logs` (Security Advisor: ERROR
--   rls_disabled_in_public). Siapa pun yang memegang kunci anon bisa membaca,
--   mengubah, dan menghapus nama, nomor HP, dan embedding wajah anggota.
-- - Kunci anon legacy yang dipakai server ikut bocor di riwayat git repo
--   publik (commit c3b7558d, Februari 2026) dan masih aktif.
-- - feature_flags dan lark_directory memakai policy `using (true)` untuk semua
--   peran, termasuk anon — saklar geofence bisa digeser siapa pun.
--
-- Semua akses data ada di server (frontend tidak pernah memanggil Supabase
-- langsung), dan secret key melewati RLS. Jadi model yang benar: RLS menyala
-- di semua tabel, TANPA policy untuk anon/authenticated.
--
-- Langkah sesudahnya (manual, dashboard): Project Settings → API Keys →
-- matikan legacy JWT keys, supaya kunci yang bocor tidak bisa dipakai sama
-- sekali, termasuk ke fitur yang tidak dilindungi RLS.

alter table public.users enable row level security;
alter table public.attendance_logs enable row level security;

drop policy if exists feature_flags_read on public.feature_flags;
drop policy if exists feature_flags_write on public.feature_flags;
drop policy if exists lark_directory_read on public.lark_directory;

-- client_perf sudah RLS tanpa policy sejak dibuat (2026-09-26_client_perf.sql).
