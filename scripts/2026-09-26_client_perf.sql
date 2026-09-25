-- Data performa dari perangkat pengguna (RUM), dikirim oleh
-- frontend/js/observability.js ke POST /api/rum.
-- Dijalankan lewat Supabase SQL Editor. Aman diulang.
--
-- Kenapa tabel, bukan Sentry: pengurus melapor web terasa sangat lambat di HP
-- mereka, dan kita belum tahu penyebabnya — RAM HP, Tailwind Play CDN yang
-- mengompilasi CSS di dalam browser, MediaPipe + kamera + iframe Lark yang
-- berjalan bersamaan di kiosk, atau jaringan venue (MASTERPLAN §2.2). Untuk
-- menjawabnya perlu data per perangkat yang bisa di-query dengan SQL biasa,
-- dan satu malam Gibbor (±16 HP sebagai kiosk) bisa menghasilkan ratusan
-- snapshot — terlalu mahal untuk kuota Sentry, yang lebih berharga untuk error.
--
-- Sampai skrip ini dijalankan, /api/rum tetap menjawab 202 dan hanya mencatat
-- peringatan sekali di log server. Tidak ada yang rusak kalau urutannya terbalik.

create table if not exists client_perf (
  id                    bigserial primary key,
  created_at            timestamptz not null default now(),

  -- Identitas: label perangkat (kiosk-03 / anon-xxxxxx), halaman, jenis snapshot.
  device                text,
  page                  text,
  phase                 text,          -- 'load' | 'final' | 'periodic'
  release               text,          -- commit yang sedang berjalan di server
  visible_ms            bigint,        -- berapa lama halaman sudah terbuka

  -- Navigation timing dokumen
  ttfb_ms               integer,
  dom_content_loaded_ms integer,
  load_ms               integer,
  transfer_kb           numeric,

  -- Web Vitals (null di Safari untuk LCP/INP — itu wajar, bukan bug)
  fcp_ms                integer,
  lcp_ms                integer,
  cls                   numeric,
  inp_ms                integer,       -- perkiraan: interaksi terlama

  -- Long task: pada phase 'periodic' angkanya per interval 15 menit,
  -- pada 'load'/'final' angkanya sepanjang umur halaman.
  longtask_count        integer,
  longtask_total_ms     bigint,
  longtask_max_ms       integer,

  -- Resource: maksimal 6 yang paling lambat, [{host, path, initiator, duration_ms, transfer_kb}]
  resource_count        integer,
  resource_transfer_kb  numeric,
  resources             jsonb,

  -- Perangkat & jaringan
  device_memory_gb      numeric,
  cpu_cores             integer,
  effective_type        text,
  downlink_mbps         numeric,
  rtt_ms                integer,
  save_data             boolean,
  viewport              text,
  dpr                   numeric,
  user_agent            text,
  js_heap_used_mb       numeric,
  js_heap_limit_mb      numeric,

  -- Field tambahan (seq, interval_ms, dan field baru di masa depan) supaya
  -- JS baru tidak perlu menunggu migrasi baru.
  extra                 jsonb
);

comment on table client_perf is
  'Snapshot performa dari browser (RUM). Satu baris = satu kiriman /api/rum.';

create index if not exists client_perf_created_at_idx on client_perf (created_at);
create index if not exists client_perf_device_created_at_idx on client_perf (device, created_at);

-- RLS: server memakai kunci anon, dan kunci itu hanya hidup di VPS — tidak
-- pernah dikirim ke peramban jemaat. Alasannya sama dengan
-- scripts/2026-09-18_feature_flags_rls.sql: tanpa policy, PostgREST diam-diam
-- menolak insert/select. Tidak ada policy update/delete: data ini hanya
-- ditambah; pembersihan dilakukan manual dari SQL Editor (lihat retensi di bawah).
alter table client_perf enable row level security;

drop policy if exists client_perf_insert on client_perf;
create policy client_perf_insert
  on client_perf for insert
  with check (true);

drop policy if exists client_perf_read on client_perf;
create policy client_perf_read
  on client_perf for select
  using (true);

-- ---------------------------------------------------------------------------
-- Contoh query: p75 LCP dan long task per perangkat, Sabtu terakhir
-- 16:00–19:00 WIB (jendela ibadah + antrian check-in).
-- ---------------------------------------------------------------------------
--
-- with sabtu as (
--   select (date_trunc('week', now() at time zone 'Asia/Jakarta') + interval '5 days')::date
--          - case when extract(isodow from now() at time zone 'Asia/Jakarta') < 6
--                 then 7 else 0 end as tgl
-- )
-- select
--   device,
--   count(*)                                                          as snapshot,
--   percentile_cont(0.75) within group (order by lcp_ms)              as p75_lcp_ms,
--   percentile_cont(0.75) within group (order by longtask_total_ms)   as p75_longtask_total_ms,
--   max(longtask_max_ms)                                              as longtask_terlama_ms,
--   min(device_memory_gb)                                             as ram_gb,
--   mode() within group (order by effective_type)                     as jaringan
-- from client_perf, sabtu
-- where phase = 'load'
--   and created_at >= (sabtu.tgl + time '16:00') at time zone 'Asia/Jakarta'
--   and created_at <  (sabtu.tgl + time '19:00') at time zone 'Asia/Jakarta'
-- group by device
-- order by p75_lcp_ms desc nulls last;
--
-- Resource paling lambat (Tailwind CDN / MediaPipe / Google Fonts?):
--
-- select r->>'host' as host, count(*) as muncul,
--        percentile_cont(0.75) within group (order by (r->>'duration_ms')::numeric) as p75_ms
-- from client_perf, jsonb_array_elements(resources) r
-- where created_at > now() - interval '7 days'
-- group by 1 order by p75_ms desc;

-- ---------------------------------------------------------------------------
-- Retensi: data performa lebih dari 180 hari tidak lagi berguna untuk
-- membandingkan acara. Jalankan manual sesekali (atau jadwalkan via pg_cron):
--
-- delete from client_perf where created_at < now() - interval '180 days';
