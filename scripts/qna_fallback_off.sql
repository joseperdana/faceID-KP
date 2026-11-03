-- Tutup lagi jalur cadangan. Jalankan setelah acara (atau setelah web KP pulih).
revoke execute on function
  qna_state(), qna_submit(text, uuid), qna_public_list(uuid),
  qna_vote(uuid, uuid, boolean), qna_display(), qna_admin_list(text),
  qna_admin_act(text, uuid, text), qna_admin_screen(text, text),
  qna_admin_settings(text, boolean, text, text)
  from anon;
