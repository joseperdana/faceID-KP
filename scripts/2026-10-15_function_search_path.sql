-- Kunci search_path dua fungsi yang ditandai Supabase Security Advisor
-- (lint 0011_function_search_path_mutable).
--
-- Tanpa search_path tetap, fungsi memakai search_path milik pemanggilnya.
-- Peran yang bisa membuat objek di skema lain bisa "membayangi" nama tabel
-- atau operator yang dipakai fungsi. Diset ke `public` (bukan string kosong)
-- karena ekstensi vector terpasang di public, dan match_faces memakai tipe
-- serta operator jaraknya tanpa nama skema.

alter function public.match_faces(vector, double precision, integer) set search_path = public;
alter function public.set_feature_flag_updated_at() set search_path = public;
