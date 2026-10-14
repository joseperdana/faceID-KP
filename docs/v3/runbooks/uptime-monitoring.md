# Runbook: pemantauan uptime dari luar

**Tujuan:** kalau `/health` tidak menjawab 200 selama beberapa menit, HP pengurus berbunyi. Tanpa ini, pertanyaan "server yang mati, atau jaringan venue?" tidak bisa dijawab. Itu yang terjadi saat Gibbor.

**Yang dicek:** `GET https://<domain>/health` setiap 60 detik dari luar server.

`/health` sengaja membalas **503** kalau database atau model wajah bermasalah (`routers/observability.py`). Jadi monitor harus menganggap **semua status selain 2xx sebagai gagal**, bukan hanya timeout. Proses yang hidup tapi modelnya gagal dimuat tetap harus membunyikan alarm, karena absensi wajah lumpuh total.

---

## Pilihan utama: Sentry Uptime Monitoring

Proyek ini sudah memakai Sentry. Monitor uptime masuk ke tempat yang sama dengan error aplikasi, jadi satu tautan cukup untuk melihat keduanya.

**Kuota:** semua plan Sentry, termasuk yang gratis, mendapat **1 monitor uptime**. Monitor tambahan berbayar ($1 per monitor di plan Team/Business). Satu monitor cukup untuk kebutuhan kita.
Sumber: [Sentry pricing](https://docs.sentry.io/pricing/)

### Langkah

1. **Cek dulu apakah sudah ada.** Sentry otomatis membuat monitor untuk hostname yang paling sering muncul di error. Buka **Monitors** di sidebar Sentry. Kalau sudah ada monitor untuk domain kita, sunting monitor itu (langkah 3), jangan buat yang kedua (kuota gratis hanya satu).
2. Buka [sentry.io/monitors/new](https://sentry.io/monitors/new/) → pilih **Uptime Monitor**.
3. Isi:

   | Kolom | Nilai | Alasan |
   |---|---|---|
   | URL | `https://<domain>/health` | Mengecek DB dan model, bukan sekadar halaman statis |
   | Method | `GET` | |
   | Interval | `1 minute` | Pilihan terpendek yang tersedia |
   | Timeout | `10` detik | Maksimum 30 detik. `/health` sehat menjawab jauh di bawah 1 detik; 10 detik sudah berarti ada masalah |
   | Failure tolerance | `3` (bawaan) | Alarm setelah 3 kegagalan berturut-turut (sekitar 3 menit). Satu kali gagal karena jaringan sesaat tidak membangunkan orang |
   | Recovery tolerance | `1` (bawaan) | Pulih setelah 1 kali sukses |
   | Project / Environment | project faceid, `production` | |

   Sentry menganggap status di luar 2xx, timeout, dan gagal DNS sebagai kegagalan. Redirect 3xx diikuti. Artinya 503 dari `/health` otomatis terhitung gagal.
4. **Buat alert:** masuk **Alerts → Create Alert**, pilih jenis untuk uptime/downtime issue, lalu tambahkan aksi:
   - **Email** ke alamat Jose dan satu pengurus cadangan.
   - **Telegram** (opsional) lewat integrasi *Telegram Alerts Bot*: **Settings → Integrations → Telegram Alerts Bot**. Integrasi ini dibuat dan dirawat pihak ketiga, bukan Sentry. Kalau tidak mau memasang integrasi pihak ketiga, pakai UptimeRobot di bawah untuk Telegram.

Sumber: [Uptime Monitoring](https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/), [Uptime Alert Configuration](https://docs.sentry.io/product/alerts/create-alerts/uptime-alert-config/), [Telegram Alerts Bot](https://docs.sentry.io/organization/integrations/notification-incidents/telegram-alerts-bot/)

---

## Cadangan: UptimeRobot (gratis)

Paket gratis: **50 monitor, interval 5 menit**, notifikasi lewat email, Telegram, Discord, Slack, dan webhook. UptimeRobot menyebut paket ini cocok untuk proyek hobi dan nirlaba. Interval 5 menit lebih kasar dari Sentry, tetapi Telegram-nya bawaan. Kombinasi yang disarankan: **Sentry (1 menit, email) + UptimeRobot (5 menit, Telegram)**. Kalau salah satu layanan pemantau bermasalah, yang lain masih jalan.
Sumber: [UptimeRobot pricing](https://uptimerobot.com/pricing/)

### Langkah

1. Daftar di uptimerobot.com (akun atas nama email KP, bukan email pribadi).
2. **Integrations → Telegram**: ikuti tautan bot, tekan Start di Telegram, lalu kembali ke UptimeRobot. Lakukan juga untuk email cadangan.
3. **Add New Monitor**:
   - Tipe: **Keyword**
   - URL: `https://<domain>/health`
   - Keyword: `"status":"ok"`, dengan kondisi *alert when keyword does NOT exist*
   - Interval: 5 menit
   - Alert contacts: Telegram + email

   Kenapa Keyword, bukan HTTP biasa: kita ingin alarm untuk *degraded* (503, isi `"status":"degraded"`), bukan hanya saat server mati. Mencari teks `"status":"ok"` menangkap keduanya tanpa bergantung pada cara UptimeRobot menafsirkan kode status.

---

## Uji alarm (wajib sekali setelah pemasangan)

Kriteria selesai Fase 0 menyebut alarm harus **terbukti sampai ke HP**. Monitor yang belum pernah diuji belum bisa dianggap berfungsi.

> **Jangan pernah lakukan ini hari Sabtu pukul 15:00–19:00 WIB**, atau saat ada acara, retret, atau registrasi yang sedang berjalan. Mematikan layanan berarti kiosk dan dashboard mati selama pengujian.

Waktu yang cocok: hari kerja, malam hari. Beri tahu grup pengurus 10 menit sebelumnya.

1. Catat jam mulai.
2. Di VPS:
   ```bash
   sudo systemctl stop faceid
   ```
3. Tunggu **4 menit** jika hanya menguji Sentry (3 kegagalan × 1 menit, ditambah jeda). Jika sekaligus menguji UptimeRobot, tunggu **7 menit**, karena intervalnya 5 menit.
4. Pastikan notifikasi masuk: email Sentry, lalu Telegram. Catat jam masuknya.
5. Nyalakan kembali:
   ```bash
   sudo systemctl start faceid
   ```
6. Model wajah butuh waktu untuk dimuat. Tunggu sampai `/health` membalas `"status":"ok"`, biasanya dalam 90 detik:
   ```bash
   curl -sS https://<domain>/health
   ```
7. Pastikan notifikasi **pulih** juga masuk.
8. Tulis hasilnya di bawah.

| Tanggal | Mulai stop | Email Sentry masuk | Telegram masuk | Pulih masuk | Oleh |
|---|---|---|---|---|---|
| [ISI] | [ISI] | [ISI] | [ISI] | [ISI] | [ISI] |

Kalau notifikasi tidak masuk dalam waktu di atas, periksa: alamat email di alert, folder spam, apakah bot Telegram sudah di-Start, dan apakah monitor berstatus aktif (bukan paused).
