-- Saklar fitur yang bisa diubah pengurus dari dashboard, tanpa deploy.
-- Dijalankan lewat Supabase SQL Editor. Aman diulang.
--
-- Tabel ini sengaja dibiarkan KOSONG setelah dibuat. Selama sebuah key belum
-- punya baris, aplikasi memakai nilai bawaannya (dari .env untuk geofence,
-- menyala untuk sisanya) — sehingga men-deploy fitur ini tidak mengubah
-- perilaku apa pun sampai ada yang benar-benar menggeser saklarnya.

create table if not exists feature_flags (
  key        text primary key,
  enabled    boolean not null,
  updated_at timestamptz not null default now()
);

comment on table feature_flags is
  'Saklar fitur per acara. Baris yang tidak ada berarti "pakai nilai bawaan aplikasi".';

create or replace function set_feature_flag_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists feature_flags_touch on feature_flags;
create trigger feature_flags_touch
  before update on feature_flags
  for each row execute function set_feature_flag_updated_at();
