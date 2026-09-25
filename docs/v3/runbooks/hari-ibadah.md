# Runbook Hari Ibadah

Untuk ibadah Sabtu 17:00 dan acara besar. Dibuka di HP penanggung jawab teknis (PJ). Pegangan utamanya: **antrean tidak boleh berhenti.** Kalau ragu, pakai jalur cadangan dulu, selidiki belakangan.

Tautan yang perlu dibuka (isi sekali, simpan sebagai bookmark):
- Health: `https://<domain>/health`
- Dashboard Grafana "Hari Ibadah": `[ISI: tautan]`
- Sentry Issues + Monitors: `[ISI: tautan]`
- Form Lark langsung (tanpa lewat kiosk): `[ISI: tautan]`

---

## T-60 menit (16:00)

- [ ] **Health hijau.** Buka `/health` dari HP pakai **data seluler**. Harus `"status":"ok"`. Kalau `degraded`, lihat bagian `checks` lalu hubungi Jose sekarang, jangan tunggu 16:45.
- [ ] **Uptime hijau** di Sentry Monitors.
- [ ] **Dashboard Grafana terbuka** di laptop multimedia: rentang *Last 3 hours*, refresh 30 detik.
- [ ] **Tidak ada deploy** sejak Sabtu 12:00. Kalau ada yang ingin deploy, tunda sampai 19:00.
- [ ] **Label perangkat.** Tiap HP kiosk dibuka sekali dengan `https://<domain>/?device=kiosk-01`, `kiosk-02`, dan seterusnya. Tempel label yang sama di HP-nya (selotip kertas). Label tersimpan di browser, jadi pembukaan berikutnya tidak perlu parameter lagi. Mode penyamaran tidak menyimpan label, jadi jangan pakai mode itu.
- [ ] **Saklar fitur** di dashboard, tab *Kontrol Fitur*, sesuai acara:
  - `geofence`: ON di gereja, OFF untuk acara di luar lokasi
  - `lark_handoff`: ON hanya kalau acara memakai form Lark
  - `registration`: ON hanya kalau ada pendaftaran anggota baru
  - `photobooth`: sesuai rencana

  Perubahan saklar butuh sampai 30 detik untuk sampai ke semua kiosk.
- [ ] **Jaringan tiap kiosk dicatat**, Wi-Fi gereja atau seluler: `kiosk-01 = [ISI]`, `kiosk-02 = [ISI]`, dan seterusnya. Saat Gibbor informasi ini tidak ada, dan tanpa itu kita tidak bisa membedakan masalah jaringan dari masalah server.
- [ ] **Baterai** minimal 80%, charger atau powerbank terpasang, layar diatur tidak mati otomatis.
- [ ] **Browser:** Chrome, bukan browser bawaan WhatsApp/Instagram. Aplikasi lain ditutup supaya RAM HP lega.
- [ ] **Uji kamera** di tiap kiosk: kamera menyala dan satu wajah pengurus terbaca.
- [ ] **Cadangan kertas** (daftar hadir + pulpen) ada di setiap meja kiosk. Petugas kiosk tahu letak tombol **cari manual** di kiosk.

## Selama 16:30–17:15: yang dipantau

| Panel Grafana | Normal | Perlu perhatian |
|---|---|---|
| RAM tersedia | > 400 MB | < 200 MB |
| Swap: batang swap-in | nyaris kosong | batang terus muncul |
| nginx 499/502/504 | kosong | ada batang, terutama 504 |
| Durasi `/api/recognize` p95 | < 800 ms | > 800 ms berturut-turut |
| 429 per menit | kosong | ada batang |
| Koneksi ke Supabase putus | kosong | ada batang (pola Gibbor) |

**Aturan terpenting:** begitu ada yang terasa aneh, **tulis jamnya** di grup panitia dengan format `HH:MM kiosk-XX gejala`, misalnya `17:21 kiosk-03 scan muter terus`. Satu baris ini lebih berharga daripada ingatan besok pagi.

## Gejala → tindakan

| Gejala | Kemungkinan penyebab | Tindakan pertama | Cadangan |
|---|---|---|---|
| **Kiosk lambat** (scan > 5 detik) | Hanya satu kiosk: sinyal atau HP. Semua kiosk: server sibuk atau macet (Gibbor) | Lihat panel 504 dan p95. Satu kiosk saja: pindah jaringan lalu muat ulang halaman. Semua kiosk: lapor Jose. **Jangan muat ulang semua kiosk bersamaan**, karena itu menambah beban server | Tombol cari manual. Kalau manual juga lambat, pakai kertas |
| **Pesan 429 / "terlalu banyak permintaan"** | Rate limit per IP: banyak kiosk di satu Wi-Fi berbagi jatah | Pindahkan sebagian kiosk ke data seluler | Kertas (check-in manual juga kena batas yang sama) |
| **Error server / 5xx / 504** | Aplikasi macet atau Supabase bermasalah | Buka `/health`. Lihat Sentry dan panel "Koneksi ke Supabase putus". Restart hanya boleh diputuskan Jose, dan hanya kalau 504 terus muncul ≥ 3 menit **dan** `/health` tidak menjawab: `sudo systemctl restart faceid` (sekitar 90 detik mati) | Kertas, langsung. Jangan menunggu server |
| **Form Lark tidak terbuka** | Kiosk macet: Lark baru muncul setelah server menjawab (dugaan kuat untuk Gibbor). Atau jaringan, atau Lark sendiri | Buka tautan form Lark langsung di tab lain. Terbuka: masalahnya di server kita, ikuti baris 5xx. Tidak terbuka: jaringan atau Lark | Tautan/QR form Lark cetak. Matikan `lark_handoff` kalau mengganggu antrean |
| **Kamera hitam** | Izin kamera ditolak, kamera dipakai aplikasi lain, dibuka di browser dalam aplikasi, atau bukan `https://` | Ketuk ikon gembok → izinkan kamera → muat ulang. Tutup aplikasi kamera lain. Buka di Chrome | Cari manual |
| **Halaman tidak terbuka sama sekali** | Server mati, atau jaringan venue | Buka `/health` dari HP sendiri memakai data seluler. Gagal juga: server (alarm uptime seharusnya berbunyi), hubungi Jose. Berhasil: jaringan venue | Pindah ke seluler. Kertas |

## T+30 menit (sekitar 17:45)

Kalau semuanya lancar, cukup tulis "aman" di grup. Kalau ada gangguan, kerjakan **malam itu juga**, selagi ingatan masih segar:

1. Kumpulkan dari grup semua baris `HH:MM kiosk-XX gejala`. Tentukan **jam mulai dan jam selesai** gangguan setepat mungkin.
2. Screenshot dashboard Grafana untuk rentang itu.
3. Salin tautan issue Sentry yang muncul di rentang itu.
4. Catat jaringan tiap kiosk (dari checklist T-60).
5. Jalankan pengumpul log di VPS, dengan bantalan 1 jam di kedua sisi:
   ```bash
   sudo bash scripts/ops/collect_incident.sh --since "YYYY-MM-DD 16:00" --until "YYYY-MM-DD 19:00"
   ```
   Log nginx dirotasi setiap hari dan dihapus setelah sekitar 14 hari. Jangan ditunda.
6. Tulis ringkasannya dengan format `docs/v3/postmortem-gibbor-2026.md`.
