-- Revisi 13 Nov: admin memilih pesan pembuka (acak / dari daftar / tulis sendiri)
-- dan efek suara saat menampilkan pertanyaan. Jalankan SETELAH 2026-11-04_qna.sql.
-- Aman diulang — tapi seperti migrasi sebelumnya, menjalankannya ulang menutup
-- kembali jalur cadangan (anon dicabut).
--
-- Pesan dan efek disimpan di baris pertanyaan, bukan dikirim lewat SSE, supaya
-- display yang dimuat ulang dan jalur cadangan (polling) membaca hal yang sama.

alter table qna_questions add column if not exists intro text
  check (intro is null or char_length(intro) between 1 and 120);
alter table qna_questions add column if not exists sfx text
  check (sfx is null or sfx in ('ding', 'tada', 'confetti'));

-- Tanda tangan berubah (dua parameter baru), jadi versi lama dibuang: kalau
-- dibiarkan, PostgREST bisa memilih overload yang salah.
drop function if exists qna_admin_act(text, uuid, text);

create or replace function qna_admin_act(
  p_pin text, p_id uuid, p_action text,
  p_intro text default null, p_sfx text default null
) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare
  v_status text;
  v_intro  text := nullif(btrim(coalesce(p_intro, '')), '');
begin
  if not qna__is_admin(p_pin) then raise exception 'forbidden'; end if;
  -- Dua admin menekan tombol bersamaan: antre di baris pengaturan supaya
  -- indeks "satu tampil" tidak berujung error 23505 mentah.
  perform 1 from qna_settings where id = 1 for update;
  select status into v_status from qna_questions where id = p_id for update;
  if v_status is null then raise exception 'not_found'; end if;

  if p_action = 'approve' and v_status in ('masuk', 'ditolak') then
    update qna_questions set status = 'disetujui' where id = p_id;
  elsif p_action = 'reject' and v_status in ('masuk', 'disetujui') then
    update qna_questions set status = 'ditolak' where id = p_id;
  elsif p_action = 'show' and v_status in ('disetujui', 'selesai') then
    if v_intro is not null and char_length(v_intro) > 120 then
      raise exception 'invalid_intro';
    end if;
    if p_sfx is not null and p_sfx not in ('ding', 'tada', 'confetti') then
      raise exception 'invalid_sfx';
    end if;
    -- Yang sedang tampil diturunkan dulu supaya indeks "satu tampil" tidak dilanggar.
    update qna_questions set status = 'selesai' where status = 'tampil';
    update qna_questions
      set status = 'tampil', shown_at = now(),
          decor_points = (array[10, 20, 50, 100])[1 + floor(random() * 4)::int],
          intro = v_intro, sfx = p_sfx
      where id = p_id;
    update qna_settings set hidden = false, show_nonce = show_nonce + 1, updated_at = now() where id = 1;
  elsif p_action = 'done' and v_status = 'tampil' then
    update qna_questions set status = 'selesai' where id = p_id;
    update qna_settings set hidden = false, show_nonce = show_nonce + 1, updated_at = now() where id = 1;
  else
    raise exception 'invalid_transition';
  end if;
  return jsonb_build_object('id', p_id, 'action', p_action);
end $$;

-- `votes` dikirim terpisah (null di mode hiasan) untuk lencana di kartu;
-- `points_text` sekarang pesan pembuka pilihan admin, dengan teks lama sebagai cadangan.
create or replace function qna_display() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare s qna_settings; q qna_questions; v_votes int; v_text text;
begin
  select * into s from qna_settings where id = 1;
  select * into q from qna_questions where status = 'tampil';
  if q.id is null or s.hidden then
    return jsonb_build_object('nonce', s.show_nonce, 'tts_engine', s.tts_engine, 'question', null);
  end if;
  if s.points_mode = 'upvote' then
    select count(*) into v_votes from qna_votes where question_id = q.id;
    v_text := case when v_votes > 0
      then format('Seseorang bertanya, %s teman ikut penasaran!', v_votes)
      else 'Seseorang bertanya!' end;
  else
    v_text := format('Seseorang memberikan %s poin!', coalesce(q.decor_points, 10));
  end if;
  return jsonb_build_object('nonce', s.show_nonce, 'tts_engine', s.tts_engine,
    'question', jsonb_build_object(
      'id', q.id, 'body', q.body,
      'points_text', coalesce(q.intro, v_text),
      'votes', v_votes,
      'sfx', coalesce(q.sfx, 'ding')));
end $$;

revoke all on function
  qna_admin_act(text, uuid, text, text, text), qna_display()
  from public, anon, authenticated;
grant execute on function
  qna_admin_act(text, uuid, text, text, text), qna_display()
  to service_role;

notify pgrst, 'reload schema';
