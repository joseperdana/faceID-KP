# Spec: Sistem Tanya Jawab Live Podcast KP — 14 November 2026

**Status:** draft, menunggu review
**Acara:** Persekutuan KP GKI Bromo Malang, format live podcast (3 narasumber), Sabtu 14 Nov 2026 pukul 17.00 WIB, Gedung Serbaguna, sekitar 70–130 orang.

## 1. Tujuan

Jemaat bisa mengirim pertanyaan secara anonim lewat HP tanpa install aplikasi. Panitia memfilter, lalu pertanyaan yang dipilih tampil di videotron. Saat tampil, ada suara notifikasi dan pertanyaannya dibacakan suara AI, mirip alert Saweria.

**Kriteria berhasil**
- Jemaat bisa scan QR, mengetik, dan mengirim pertanyaan dalam waktu kurang dari 15 detik, tanpa login.
- Tidak ada pertanyaan yang tampil di videotron tanpa disetujui admin.
- Sejak admin klik "Tampilkan" sampai kartu muncul + suara notifikasi berbunyi, jedanya kurang dari 2 detik.
- Bisa menampung 130 HP bersamaan tanpa mengganggu kiosk absen wajah.

**Di luar cakupan:** nama pengirim, akun jemaat, riwayat/statistik lintas acara, dan tampilan di layar selain videotron.

## 2. Keputusan

| Topik | Keputusan |
|---|---|
| Moderasi | Semua pertanyaan masuk antrean admin dulu (Sie Multimedia), tidak ada yang tampil otomatis. |
| Poin | Ada dua mode yang dipilih admin di pengaturan: **Hiasan** dan **Upvote** (lihat §5). |
| Suara AI | Default TTS browser; opsi TTS cloud (Google Cloud TTS) bisa diganti dari admin. Kalau cloud gagal, otomatis pindah ke browser. |
| Videotron | Satu halaman display dengan dua mode: `overlay` (transparan, untuk OBS) dan `full` (latar penuh). |
| Hosting | **Modul baru di web KP (FaceID-KP)** — lihat §3. |

## 3. Hosting: modul di web KP vs berdiri sendiri

**Plus kalau pakai web KP (FaceID-KP)**
- Infrastruktur sudah ada: VPS, domain, Supabase, HTTPS. Tidak perlu akun atau hosting baru.
- Login admin sudah ada (`/login` + cookie JWT, `check_admin_auth`), jadi panitia pakai password yang sama.
- Feature flag (`core/flags.py`) bisa dipakai: rute langsung terkunci 404 saat acara selesai, sama seperti photobooth.
- Rate limit `slowapi` sudah terpasang, jadi anti-spam tinggal dipakai.
- Sudah ada contoh sebelumnya (Photobooth KP45), dan sejalan dengan roadmap "KP Bromo Hub" v2.0. Fiturnya bisa dipakai ulang di acara berikutnya.
- API key TTS cloud aman tersimpan di `.env` server.

**Minus kalau pakai web KP**
- **Berbagi server dengan kiosk absen wajah di malam yang sama.** Kalau modul ini bermasalah atau deploy-nya gagal, kiosk bisa ikut down. InsightFace juga berat untuk CPU.
- Deploy harus mengikuti alur VPS dan aturan repo FaceID-KP (test, struktur router), jadi lebih lambat dibanding hosting statis.
- Realtime harus dibuat sendiri (SSE dari FastAPI) karena app belum punya WebSocket/SSE.
- Kalau VPS mati, semuanya mati; tidak ada cadangan.

**Plus/minus kalau berdiri sendiri (HTML statis + Supabase Realtime di Vercel)**
- Plus: terpisah total dari kiosk, realtime sudah tersedia dari Supabase, deploy cukup sekali `git push`.
- Minus: harus membuat auth admin sendiri, ada satu proyek lagi yang perlu dirawat, dan TTS cloud butuh Edge Function terpisah.

**Rekomendasi: modul di web KP**, dengan mitigasi berikut:
- Endpoint modul ini ringan (hanya teks, tanpa inferensi), dan kiosk hanya ramai di awal acara, sedangkan sesi tanya jawab berlangsung di akhir acara. Bebannya tidak bertumpuk.
- Deploy modul ini dibekukan paling lambat Kamis, 12 Nov 2026, lalu gladi bersih di server produksi.
- Logika halaman dibuat portabel (vanilla JS di file sendiri), jadi kalau perlu bisa dipindah ke opsi berdiri sendiri tanpa menulis ulang UI.

## 4. Arsitektur

Mengikuti pola FaceID-KP: satu router per domain, HTML statis per halaman.

```
scripts/2026-11-04_qna.sql        # tabel + fungsi qna_* (aturan bisnis)
scripts/qna_selftest.sql          # uji fungsi SQL (BEGIN … ROLLBACK)
scripts/qna_fallback_on.sql / qna_fallback_off.sql
scripts/build_qna_standalone.sh   # folder statis jalur cadangan
scripts/qna_loadtest.py
services/qna_service.py           # pemanggil RPC qna_* + pemetaan error
services/tts_service.py           # Google Cloud TTS
core/qna_bus.py                   # siaran event SSE di memori proses
routers/qna.py                    # halaman + API
frontend/qna/                     # tanya.html, tanya-admin.html, tanya-display.html,
                                  # config.js, qna-common.js, qna-api-kp.js,
                                  # qna-api-supabase.js, jemaat.js, admin.js, display.js, qna.css
```

**Rute halaman**
| Rute | Siapa | Akses |
|---|---|---|
| `/tanya` | Jemaat (QR) | Publik, terkunci flag `qna` |
| `/tanya/admin` | Sie Multimedia | `check_admin_auth` |
| `/tanya/display?mode=overlay\|full` | Laptop videotron | `check_admin_auth` (laptop login sekali) |

**Realtime:** admin dan display berlangganan `GET /api/qna/admin/stream` (Server-Sent Events). Kalau SSE putus, browser menyambung ulang otomatis; selain itu ada cadangan cek ulang state tiap 5 detik.
- Event disebar lewat antrean `asyncio` di memori proses. Koneksi SSE tidak pernah melakukan query DB, dan semua akses Supabase berjalan di handler `def` (thread pool). Ini sesuai aturan `core/flags.py`: tidak boleh ada I/O jaringan di event loop, supaya halaman kiosk `/` tidak ikut membeku.
- Produksi berjalan dengan **satu proses uvicorn** (dikonfirmasi di `scripts/deploy_vps.sh`), jadi siaran di memori sampai ke semua koneksi SSE. Kalau suatu saat diubah ke multi-worker, admin dan display tetap jalan lewat cadangan cek state 5 detik.
- Flag baru `qna` ditambahkan ke `core/flags.py` dengan bawaan **mati**. Rute `/tanya` menghasilkan 404 saat flag mati. Halaman jemaat tidak memakai SSE; di mode Upvote daftar pertanyaan di-refresh tiap 5 detik (sekitar 130 HP ≈ 26 req/detik, respons kecil; cache baru ditambahkan kalau uji beban §11 gagal).

## 5. Mode poin

Admin memilih mode di pengaturan sebelum sesi dibuka. Mode tidak boleh diganti saat sesi berjalan.

**Mode Hiasan**
- Halaman jemaat hanya berisi form kirim.
- Saat tampil, angka poin diacak dari {10, 20, 50, 100}. Teks: *"Seseorang memberikan 50 poin!"*
- Antrean admin diurutkan dari pertanyaan yang paling lama masuk.

**Mode Upvote (ala Mentimeter/Slido)**
- Halaman jemaat punya dua tab: **Kirim** dan **Pertanyaan**.
- Tab Pertanyaan hanya menampilkan pertanyaan yang **sudah disetujui** dan belum selesai dibahas, masing-masing dengan tombol ▲ dan jumlah dukungan. Pertanyaan yang masih menunggu persetujuan tidak terlihat, jadi moderasi tetap berlaku.
- Satu dukungan per HP per pertanyaan, dan bisa dibatalkan. Identitas HP = UUID acak di `localStorage`, dikunci di DB dengan unique `(question_id, device_id)`. Ini cukup untuk acara internal; trik membuka mode incognito diterima sebagai risiko.
- Antrean admin bisa diurutkan berdasarkan dukungan terbanyak (default) atau waktu.
- Saat tampil, poin = jumlah dukungan. Teks: *"Seseorang bertanya, 23 teman ikut penasaran!"* (kalau dukungannya 0: *"Seseorang bertanya!"*)

## 6. Alur & status

```
masuk ──setujui──▶ disetujui ──tampilkan──▶ tampil ──selesai──▶ selesai
  └──tolak──▶ ditolak
```

- Hanya boleh ada **satu** pertanyaan berstatus `tampil`. Kalau admin menampilkan pertanyaan lain, pertanyaan sebelumnya otomatis menjadi `selesai`.
- Admin bisa **Buka/Tutup sesi**. Saat ditutup, form jemaat menampilkan "Sesi tanya jawab belum dibuka / sudah ditutup", dan API menolak kiriman (409).
- Admin bisa **Putar ulang** (memicu ulang alert + suara) dan **Sembunyikan** (mengosongkan layar tanpa menandai selesai).

**Urutan alert di display saat ada event `tampil`:**
1. Suara notifikasi (dibangkitkan dengan Web Audio, sekitar 1,2 detik; tanpa file audio).
2. Kartu masuk dengan animasi: baris poin (§5) + isi pertanyaan.
3. TTS membacakan *"[teks poin]. [isi pertanyaan]"*.
4. Kartu tetap tampil sampai ada event `selesai`/`sembunyikan`.

## 7. Data (Supabase, proyek FaceID-KP)

```sql
qna_questions (
  id uuid pk default gen_random_uuid(),
  body text not null check (char_length(body) between 3 and 300),
  status text not null default 'masuk'
    check (status in ('masuk','disetujui','ditolak','tampil','selesai')),
  device_id uuid not null,          -- untuk rate limit, tidak pernah ditampilkan
  decor_points int,                 -- diisi saat tampil di mode Hiasan
  created_at timestamptz default now(),
  shown_at timestamptz
)
qna_votes (
  question_id uuid references qna_questions on delete cascade,
  device_id uuid,
  created_at timestamptz default now(),
  primary key (question_id, device_id)
)
qna_settings (            -- satu baris
  id int pk check (id = 1),
  session_open bool default false,
  points_mode text default 'hiasan' check (points_mode in ('hiasan','upvote')),
  tts_engine text default 'browser' check (tts_engine in ('browser','cloud')),
  hidden bool default false,        -- layar dikosongkan tanpa menandai selesai
  show_nonce int default 0          -- naik setiap show/done/hide/replay; display bereaksi saat berubah
)
qna_secret (id int pk check (id = 1), pin_hash text)  -- PIN admin jalur cadangan (bcrypt)
```

RLS menyala di semua tabel `qna_*` tanpa policy (sesuai `2026-10-15_rls_lockdown.sql`). Normalnya hanya backend (secret key) yang boleh mengeksekusi fungsi `qna_*`. Partial unique index menjamin hanya ada satu baris `status = 'tampil'`.

## 8. API

Aturan bisnis (validasi, jeda per HP, transisi status, teks poin) ada di **fungsi Postgres** `qna_*` (§13). Backend KP hanya memanggil fungsi itu dengan secret key, lalu menambahkan login cookie, rate limit per IP, SSE, dan proxy TTS. Jalur cadangan memanggil fungsi yang sama langsung dari browser.

| Method & path | Akses | Fungsi |
|---|---|---|
| `GET /api/qna/state` | publik (flag) | `session_open`, `points_mode` |
| `POST /api/qna/questions` | publik (flag) | kirim `{body, device_id}` |
| `GET /api/qna/questions/public?device_id=` | publik (flag) | daftar disetujui + dukungan + `voted` (mode Upvote saja) |
| `POST /api/qna/questions/{id}/vote` | publik (flag) | `{device_id, on}`: dukung / batal dukung |
| `GET /api/qna/display` | publik | `{nonce, question\|null, tts_engine}` untuk videotron |
| `GET /api/qna/admin/questions` | admin | semua pertanyaan + dukungan + pengaturan |
| `POST /api/qna/admin/questions/{id}/{action}` | admin | `approve`, `reject`, `show`, `done` |
| `POST /api/qna/admin/screen/{action}` | admin | `hide`, `replay` |
| `PATCH /api/qna/admin/settings` | admin | buka/tutup sesi, mode poin, mesin TTS |
| `GET /api/qna/admin/stream` | admin | SSE: `changed {kind}` dengan kind `questions` / `display` / `settings` |
| `POST /api/qna/admin/tts` | admin | `{text}` → MP3 dari Google Cloud TTS (`id-ID`), timeout 4 detik |

**Validasi & anti-spam**
- Isi pertanyaan di-trim, panjang 3–300 karakter, dan di-escape saat render.
- **Utamanya jeda 30 detik per `device_id`**, ditegakkan di fungsi `qna_submit`.
- `slowapi` per IP dibuat longgar (300 kirim/menit, 300 vote/menit) karena satu WiFi gereja = satu IP (NAT). Batas per IP hanya untuk menahan skrip, bukan untuk membatasi orang.
- Di sisi klien, tombol Kirim nonaktif selama jeda dengan hitung mundur.

## 9. Suara AI

- **Browser:** `speechSynthesis` dengan suara `id-ID` pertama yang tersedia, (misal "Google Bahasa Indonesia" di Chrome, "Damayanti" di macOS). Suara dipilih lewat dropdown di layar persiapan halaman display (sebelum tombol "Aktifkan suara"), lengkap dengan tombol uji. Pilihannya disimpan di `localStorage` laptop itu, karena daftar suara berbeda di tiap perangkat.
- **Cloud:** display memanggil `POST /api/qna/tts`, lalu memutar MP3-nya. API key tersimpan di `.env` (`GOOGLE_TTS_API_KEY`). Kalau gagal atau lebih dari 4 detik, display pakai suara browser dan memberi tanda kecil di admin.
- **Autoplay:** display menampilkan layar persiapan dengan tombol "Aktifkan suara & mulai" (Chrome memblokir audio tanpa interaksi). Status koneksi tampil sebagai titik kecil di pojok display; indikator koneksi admin ada di halaman admin sendiri. Tidak ada laporan kehadiran display ke admin (YAGNI). Saat gladi bersih, operator videotron mengecek titiknya.

## 10. Penanganan error

| Kondisi | Perilaku |
|---|---|
| SSE putus | Browser menyambung ulang + cadangan cek state tiap 5 detik; halaman admin dan display masing-masing menampilkan status koneksinya. SSE ditutup server tiap 10 menit lalu tersambung ulang otomatis, dengan ping 15 detik dan header `X-Accel-Buffering: no` supaya nginx tidak memutus atau menahan stream. |
| Kiriman gagal (jaringan) | Teks tetap di form, muncul pesan "Gagal kirim, coba lagi". |
| Kirim saat sesi tutup | 409, form menampilkan "Sesi belum dibuka". |
| Kena jeda/rate limit | 429 dengan `retry_after`, muncul hitung mundur. |
| TTS cloud gagal | Pindah ke suara browser. |
| Tidak ada suara id-ID di laptop | Pakai suara default + peringatan di admin saat gladi bersih. |

## 11. Pengujian

- **Unit/API (pytest, mengikuti `tests/` yang sudah ada):** transisi status (termasuk aturan hanya satu `tampil`), sesi tutup → 409, validasi panjang, jeda per device, vote unik + batal vote, endpoint admin menolak tanpa cookie, endpoint publik tidak pernah mengembalikan `masuk`/`ditolak`/`device_id`.
- **E2E (Playwright, sudah ada di requirements):** jemaat kirim → admin setujui → tampilkan → display menampilkan kartu; alur upvote.
- **Beban:** skrip 130 kiriman + polling 5 detik selama 5 menit, sambil kiosk diuji; latensi p95 < 500 ms.
- **Gladi bersih (paling lambat Kamis, 12 Nov):** laptop dan videotron asli, OBS Browser Source mode `overlay`, cek suara TTS dan volume ruangan, scan QR dari beberapa HP dengan kuota dan WiFi gereja.

## 12. Hari H (checklist operasional)

1. Nyalakan flag `qna`, pilih mode poin, uji suara.
2. Laptop videotron: login → buka `/tanya/display?mode=...` → klik "Aktifkan suara".
3. QR ke `/tanya` disiapkan di slide/videotron.
4. Saat sesi tanya jawab: admin **Buka sesi**. Setelah selesai: **Tutup sesi**, lalu matikan flag.

## 13. Jalur cadangan (kalau web KP bermasalah)

**Tujuan:** kalau web KP tidak bisa diakses di hari H, sistem pindah ke situs statis dalam waktu kurang dari 5 menit **tanpa kehilangan pertanyaan** yang sudah masuk.

**Kenapa bisa cepat:** semua aturan ada di fungsi Postgres `qna_*` di proyek Supabase yang sama. Halaman jemaat/admin/display memanggil backend lewat **adapter** JS dengan antarmuka yang sama:
- `qna-api-kp.js` (fetch ke FastAPI + SSE);
- `qna-api-supabase.js` (fetch langsung ke `/rest/v1/rpc/qna_*` dengan publishable key + polling 2 detik).

`config.js` menentukan adapter mana yang dipakai. Skrip `scripts/build_qna_standalone.sh` menyalin halaman yang sama dan mengganti `config.js`, hasilnya folder statis siap diunggah ke Netlify Drop.

**Perbedaan di jalur cadangan**
- Login admin memakai **PIN** (frasa minimal 12 karakter) yang diperiksa fungsi `qna__is_admin` dengan bcrypt, bukan cookie KP.
- Realtime diganti polling 2 detik, sehingga jeda tampil maksimal sekitar 2 detik.
- TTS cloud tidak tersedia; display otomatis memakai suara browser.
- Tidak ada rate limit per IP; anti-spam hanya jeda per HP di fungsi `qna_submit`.

**Keamanan:** pintu publik **tertutup secara bawaan**. `scripts/qna_fallback_on.sql` memberi `execute` fungsi `qna_*` ke role `anon` dan sekaligus menetapkan PIN. `scripts/qna_fallback_off.sql` mencabutnya kembali. Selama web KP sehat, kunci publishable tidak bisa memanggil apa pun di modul ini.

**Kalau Supabase sendiri down:** kedua jalur ikut mati. Rencana terakhirnya, MC membacakan pertanyaan yang ditulis di kertas, atau memakai Google Form cadangan (link disiapkan oleh panitia).

**Persiapan sebelum hari H:**
- Situs cadangan sudah di-deploy dan dites saat gladi bersih.
- **Dua QR dicetak/disiapkan** (utama `/tanya` dan cadangan URL Netlify).
- PIN disimpan oleh 2 orang panitia.

## 14. Revisi 13 Nov 2026

- Pesan sukses di halaman jemaat cukup "Terkirim!".
- **Pesan pembuka** menggantikan "Seseorang memberikan N poin!". Admin memilih di toolbar: **Acak** (bawaan), salah satu dari 12 pesan (`Qna.INTROS`), atau **Tulis sendiri** (maks. 120 karakter). Pilihan berlaku untuk setiap klik **Tampilkan**; disimpan di `qna_questions.intro`. Kalau kosong, teks lama dipakai sebagai cadangan.
- **Efek suara** sintetis (Web Audio, tanpa file): `ding`, `tada`, `confetti`, atau Acak; disimpan di `qna_questions.sfx`.
- Display membacakan pesan pembuka dan isi pertanyaan **terpisah dengan jeda 0,7 detik**.
- Mode upvote: jumlah dukungan tampil sebagai lencana "▲ N teman ikut penasaran" di kartu (tidak dibacakan).
- Migrasi: `scripts/2026-11-13_qna_intro.sql` (kolom baru, `qna_admin_act` jadi 5 parameter, `qna_display` mengembalikan `votes` & `sfx`). Skrip `qna_fallback_on/off.sql` dan `qna_selftest.sql` ikut diperbarui.
