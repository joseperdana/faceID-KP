-- HARI H, hanya kalau web KP bermasalah: buka fungsi qna_* untuk kunci
-- publishable supaya situs cadangan (Netlify) bisa bekerja. PIN harus sudah
-- diisi lewat qna_set_pin.sql. Matikan lagi dengan qna_fallback_off.sql.
do $$
begin
  if (select pin_hash from qna_secret where id = 1) is null then
    raise exception 'PIN admin belum diisi. Jalankan qna_set_pin.sql dulu.';
  end if;
end $$;
grant execute on function
  qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
  qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
  qna_admin_act(text, uuid, text, text, text), qna_admin_screen(text, text),
  qna_admin_settings(text, boolean, text, text)
  to anon;
