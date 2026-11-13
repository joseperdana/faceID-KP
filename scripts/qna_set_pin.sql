-- PIN admin untuk jalur cadangan (situs statis). Jalankan saat gladi bersih,
-- simpan frasanya di DUA orang panitia. Minimal 12 karakter: fungsi admin
-- terbuka ke internet selama jalur cadangan aktif.
do $$
declare v_pin constant text := 'GANTI-DENGAN-FRASA-PANJANG';
begin
  if v_pin = 'GANTI-DENGAN-FRASA-PANJANG' or char_length(v_pin) < 12 then
    raise exception 'Ganti v_pin dengan frasa minimal 12 karakter dulu.';
  end if;
  update qna_secret set pin_hash = extensions.crypt(v_pin, extensions.gen_salt('bf')) where id = 1;
end $$;
