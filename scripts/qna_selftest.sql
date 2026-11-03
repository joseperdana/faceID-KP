-- Uji fungsi tanya jawab. Jalankan di Supabase SQL Editor SETELAH
-- 2026-11-04_qna.sql. Semuanya di dalam transaksi yang di-ROLLBACK: aman
-- dijalankan di produksi, tidak ada data yang tertinggal.
-- Lulus = muncul NOTICE "qna_selftest: semua lulus". Gagal = ERROR "GAGAL: ...".
begin;

-- Kondisi awal yang diketahui, apa pun isi tabel sebelumnya.
delete from qna_votes;
delete from qna_questions;
update qna_settings set session_open = false, points_mode = 'hiasan', tts_engine = 'browser',
  hidden = false, show_nonce = 0 where id = 1;
update qna_secret set pin_hash = extensions.crypt('pin-uji-panjang-123', extensions.gen_salt('bf')) where id = 1;
select set_config('request.jwt.claims', '', true);

create function pg_temp.expect_error(p_sql text, p_expected text) returns void
language plpgsql as $$
begin
  execute p_sql;
  raise exception 'GAGAL: "%" seharusnya ditolak dengan "%"', p_sql, p_expected;
exception when others then
  if sqlerrm not like p_expected then raise; end if;
end $$;

create function pg_temp.check(p_ok boolean, p_what text) returns void
language plpgsql as $$
begin
  if not coalesce(p_ok, false) then raise exception 'GAGAL: %', p_what; end if;
end $$;

do $$
declare
  pin constant text := 'pin-uji-panjang-123';
  dev1 constant uuid := 'aaaaaaaa-0000-4000-8000-000000000001';
  dev2 constant uuid := 'aaaaaaaa-0000-4000-8000-000000000002';
  q1 uuid; q2 uuid; r jsonb;
begin
  -- Sesi tutup menolak kiriman
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', 'Halo narasumber', dev1), 'session_closed');

  -- Admin: PIN salah ditolak, PIN benar diterima
  perform pg_temp.expect_error('select qna_admin_settings(''salah'', true, null, null)', 'forbidden');
  perform qna_admin_settings(pin, false, 'upvote', null);
  perform qna_admin_settings(pin, true, null, null);
  perform pg_temp.check((qna_state() ->> 'session_open')::boolean, 'sesi terbuka');
  perform pg_temp.check(qna_state() ->> 'points_mode' = 'upvote', 'mode upvote');

  -- Mode terkunci selama sesi terbuka
  perform pg_temp.expect_error(format('select qna_admin_settings(%L, null, %L, null)', pin, 'hiasan'), 'mode_locked');

  -- Validasi isi
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', '  ab  ', dev1), 'invalid_body');
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', repeat('x', 301), dev1), 'invalid_body');

  -- Kirim + jeda per HP
  q1 := (qna_submit('  Gimana cara tahu panggilan hidup?  ', dev1) ->> 'id')::uuid;
  perform pg_temp.check((select body from qna_questions where id = q1) = 'Gimana cara tahu panggilan hidup?', 'isi di-trim');
  perform pg_temp.check((select status from qna_questions where id = q1) = 'masuk', 'status awal masuk');
  perform pg_temp.expect_error(format('select qna_submit(%L, %L)', 'Pertanyaan kedua', dev1), 'cooldown:%');
  q2 := (qna_submit('Kenapa harus ke gereja?', dev2) ->> 'id')::uuid;

  -- Daftar publik hanya yang disetujui; yang masuk tidak bisa didukung
  perform pg_temp.check(jsonb_array_length(qna_public_list(dev1)) = 0, 'pertanyaan masuk tidak publik');
  perform pg_temp.expect_error(format('select qna_vote(%L, %L, true)', q1, dev1), 'not_votable');
  perform qna_admin_act(pin, q1, 'approve');
  r := qna_public_list(dev1);
  perform pg_temp.check(jsonb_array_length(r) = 1, 'satu pertanyaan publik');
  perform pg_temp.check(r -> 0 ->> 'device_id' is null, 'device_id tidak bocor');

  -- Dukungan unik per HP, bisa dibatalkan
  perform qna_vote(q1, dev1, true);
  perform qna_vote(q1, dev1, true);
  perform pg_temp.check((qna_vote(q1, dev2, true) ->> 'votes')::int = 2, 'dua dukungan');
  perform pg_temp.check((qna_vote(q1, dev2, false) ->> 'votes')::int = 1, 'batal dukung');
  perform pg_temp.check((qna_public_list(dev1) -> 0 ->> 'voted')::boolean, 'voted untuk dev1');
  perform pg_temp.check(not (qna_public_list(dev2) -> 0 ->> 'voted')::boolean, 'tidak voted untuk dev2');

  -- Tolak lalu setujui ulang
  perform qna_admin_act(pin, q2, 'reject');
  perform pg_temp.check((select status from qna_questions where id = q2) = 'ditolak', 'ditolak');
  perform qna_admin_act(pin, q2, 'approve');

  -- Tampil: satu saja, nonce naik, teks poin upvote
  perform qna_admin_act(pin, q1, 'show');
  r := qna_display();
  perform pg_temp.check((r ->> 'nonce')::int = 1, 'nonce 1');
  perform pg_temp.check(r -> 'question' ->> 'body' = 'Gimana cara tahu panggilan hidup?', 'display isi q1');
  perform pg_temp.check(r -> 'question' ->> 'points_text' = 'Seseorang bertanya, 1 teman ikut penasaran!', 'teks upvote');
  perform qna_admin_act(pin, q2, 'show');
  perform pg_temp.check((select status from qna_questions where id = q1) = 'selesai', 'q1 otomatis selesai');
  perform pg_temp.check((select count(*) from qna_questions where status = 'tampil') = 1, 'hanya satu tampil');
  perform pg_temp.check(qna_display() -> 'question' ->> 'points_text' = 'Seseorang bertanya!', 'teks upvote nol');

  -- Kosongkan & putar ulang
  perform qna_admin_screen(pin, 'hide');
  r := qna_display();
  perform pg_temp.check(r -> 'question' = 'null'::jsonb and (r ->> 'nonce')::int = 3, 'layar kosong, nonce 3');
  perform qna_admin_screen(pin, 'replay');
  r := qna_display();
  perform pg_temp.check(r -> 'question' ->> 'id' = q2::text and (r ->> 'nonce')::int = 4, 'putar ulang q2');

  -- Selesai
  perform qna_admin_act(pin, q2, 'done');
  perform pg_temp.check(qna_display() -> 'question' = 'null'::jsonb, 'tidak ada yang tampil');
  perform pg_temp.expect_error(format('select qna_admin_screen(%L, %L)', pin, 'replay'), 'nothing_showing');
  perform pg_temp.expect_error(format('select qna_admin_act(%L, %L, %L)', pin, q1, 'done'), 'invalid_transition');
  perform pg_temp.expect_error(format('select qna_admin_act(%L, %L, %L)', pin, gen_random_uuid(), 'approve'), 'not_found');

  -- Mode hiasan: tutup + ganti mode dalam satu panggilan boleh
  perform qna_admin_settings(pin, false, 'hiasan', null);
  perform qna_admin_settings(pin, true, null, null);
  perform qna_admin_act(pin, q1, 'show');
  perform pg_temp.check(qna_display() -> 'question' ->> 'points_text' ~ '^Seseorang memberikan (10|20|50|100) poin!$', 'teks hiasan');
  perform pg_temp.check(jsonb_array_length(qna_public_list(dev1)) = 0, 'daftar publik kosong di mode hiasan');

  -- Jalur backend: service_role tanpa PIN
  perform pg_temp.expect_error('select qna_admin_list(null)', 'forbidden');
  perform set_config('request.jwt.claims', '{"role":"service_role"}', true);
  perform pg_temp.check(jsonb_array_length(qna_admin_list(null) -> 'questions') = 2, 'service_role melihat semua');
  perform set_config('request.jwt.claims', '', true);

  -- Tertutup untuk anon secara bawaan
  perform pg_temp.check(not has_function_privilege('anon', 'qna_submit(text, uuid)', 'execute'), 'anon tidak bisa qna_submit');
  perform pg_temp.check(not has_function_privilege('anon', 'qna_admin_list(text)', 'execute'), 'anon tidak bisa qna_admin_list');
  perform pg_temp.check(not has_table_privilege('anon', 'qna_questions', 'select'), 'anon tidak bisa baca tabel');

  -- Saklar jalur cadangan: skrip on/off harus menyentuh tepat 9 fungsi itu.
  declare
    fns constant text[] := array[
      'qna_state()', 'qna_submit(text, uuid)', 'qna_public_list(uuid)',
      'qna_vote(uuid, uuid, boolean)', 'qna_display()', 'qna_admin_list(text)',
      'qna_admin_act(text, uuid, text)', 'qna_admin_screen(text, text)',
      'qna_admin_settings(text, boolean, text, text)'];
    f text;
  begin
    foreach f in array fns loop
      perform pg_temp.check(has_function_privilege('service_role', f, 'execute'), 'service_role tidak punya execute: ' || f);
      perform pg_temp.check(not has_function_privilege('anon', f, 'execute'), 'anon sudah punya execute sebelum on: ' || f);
    end loop;

    -- Salinan persis dari qna_fallback_on.sql
    grant execute on function
      qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
      qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
      qna_admin_act(text, uuid, text), qna_admin_screen(text, text),
      qna_admin_settings(text, boolean, text, text)
      to anon;

    foreach f in array fns loop
      perform pg_temp.check(has_function_privilege('anon', f, 'execute'), 'fallback_on tidak memberi execute ke anon: ' || f);
    end loop;
    perform pg_temp.check(not has_function_privilege('anon', 'qna__is_admin(text)', 'execute'), 'qna__is_admin terbuka untuk anon');

    -- Salinan persis dari qna_fallback_off.sql
    revoke execute on function
      qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
      qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
      qna_admin_act(text, uuid, text), qna_admin_screen(text, text),
      qna_admin_settings(text, boolean, text, text)
      from anon;

    foreach f in array fns loop
      perform pg_temp.check(not has_function_privilege('anon', f, 'execute'), 'fallback_off belum mencabut execute anon: ' || f);
    end loop;
  end;

  raise notice 'qna_selftest: semua lulus';
end $$;

rollback;
