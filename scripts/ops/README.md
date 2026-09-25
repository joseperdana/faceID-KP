# scripts/ops — alat observability VPS (Fase 0)

Semua yang ada di sini dijalankan **manual oleh Jose di VPS**. Tidak ada yang dipasang otomatis oleh `scripts/remote_update.sh` atau GitHub Actions. Deploy aplikasi sengaja tidak menyentuh nginx, journald, maupun Alloy: kesalahan di lapisan itu bisa mematikan kamera kiosk atau memenuhi disk, jadi setiap perubahan harus dilakukan dengan sadar.

Latar belakang: `docs/v3/MASTERPLAN.md` §5 dan `docs/v3/postmortem-gibbor-2026.md`.

## Isi

| Berkas | Fungsi |
|---|---|
| `collect_incident.sh` | Mengumpulkan semua jejak di VPS untuk satu jendela waktu (journal, nginx, OOM, status layanan), lalu membuat `SUMMARY.txt` per hipotesis dan tar.gz. Hanya membaca. |
| `nginx-logformat.conf` | Format log `kp_timed`: waktu per request, waktu upstream, status upstream, label kiosk. Dipasang manual. |
| `journald-retention.conf` | Drop-in journald: log disimpan 90 hari, maksimal 1 GB, persisten. |
| `alloy/config.alloy` | Konfigurasi Grafana Alloy: metrik host dan log (faceid, systemd, kernel, nginx) ke Grafana Cloud. |
| `setup_alloy.sh` | Memasang Alloy dari repo resmi Grafana, template kredensial, dan batas memori 200 MB. |
| `grafana/hari-ibadah.json` | Dashboard "Hari Ibadah" untuk diimpor ke Grafana Cloud. |
| `../../docs/v3/runbooks/uptime-monitoring.md` | Pemantau `/health` dari luar (Sentry + UptimeRobot) dan cara menguji alarmnya. |
| `../../docs/v3/runbooks/hari-ibadah.md` | Checklist dan tabel tindakan untuk hari Sabtu dan acara besar. |

## Membawa berkas ke VPS

Sebelum branch ini di-merge dan di-deploy, salin foldernya dari laptop:

```bash
scp -r scripts/ops <user>@<ip-vps>:/tmp/kp-ops
ssh <user>@<ip-vps>
cd /tmp/kp-ops
```

Setelah di-merge ke `main` dan ter-deploy, berkasnya ada di direktori aplikasi di server, yaitu `/home/adminKPBromo/faceID-KP` (`$HOME/faceID-KP`, bukan `/var/www/faceID-KP`). Jalankan dari sana: `cd /home/adminKPBromo/faceID-KP`, lalu pakai path `scripts/ops/...`.

Perintah di bawah memakai path repo. Kalau memakai salinan di `/tmp/kp-ops`, buang awalan `scripts/ops/`.

## Urutan kerja

### 1. SEGERA: arsipkan bukti Gibbor (batas sekitar 3 Oktober 2026)

Log nginx di Ubuntu dirotasi harian dan disimpan 14 hari. Log 19 September hilang sekitar 3 Oktober.

```bash
sudo bash scripts/ops/collect_incident.sh --since "2026-09-19 16:00" --until "2026-09-19 19:00"
```

Ringkasannya langsung tampil di layar. Ambil arsipnya ke laptop (perintah persisnya dicetak di akhir):

```bash
scp <user>@<ip-vps>:/tmp/kp-incident-20260919-1600-diambil-*.tar.gz .
```

Isinya memuat IP klien dan user_id. Simpan di tempat privat, jangan di repo atau grup chat, lalu hapus dari `/tmp` di VPS.

### 2. Retensi journald (5 menit, di luar Sabtu 15:00–19:00)

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo cp scripts/ops/journald-retention.conf /etc/systemd/journald.conf.d/kp-retention.conf
sudo systemctl restart systemd-journald
journalctl --disk-usage
sudo journalctl -u faceid -n 5 --no-pager
```

### 3. Format log nginx (10 menit, suntingan manual)

Langkah lengkap ada di komentar `nginx-logformat.conf`. Ringkasnya:

```bash
sudo cp scripts/ops/nginx-logformat.conf /etc/nginx/conf.d/kp-logformat.conf
sudo cp /etc/nginx/sites-available/faceid /root/faceid.nginx.bak-$(date +%F)
sudo nano /etc/nginx/sites-available/faceid
#   di dalam blok server yang berisi "listen 443 ssl", tambahkan:
#   access_log /var/log/nginx/access.log kp_timed;
sudo nginx -t && sudo systemctl reload nginx
sudo tail -n 3 /var/log/nginx/access.log     # baris baru berakhiran rt=... urt=...
```

Jangan pernah memakai `scripts/deploy_vps.sh` untuk ini. Skrip itu khusus server kosong: ia menolak berjalan di server yang sudah terpasang, karena akan menimpa konfigurasi HTTPS.

### 4. Grafana Cloud + Alloy (30 menit)

1. Buat akun Grafana Cloud gratis (pakai email KP). Free tier: 10 ribu series metrik, 50 GB log per bulan, **retensi 14 hari**. Retensi yang lebih panjang ditangani journald di langkah 2.
2. Di VPS:
   ```bash
   sudo bash scripts/ops/setup_alloy.sh
   sudo nano /etc/alloy/grafana-cloud.env      # isi 5 nilai, petunjuk ada di dalam berkas
   sudo systemctl restart alloy
   systemctl status alloy --no-pager
   sudo journalctl -u alloy -n 50 --no-pager
   ```
3. Di Grafana Cloud → Explore, pastikan `node_memory_MemAvailable_bytes` (Prometheus) dan `{job="faceid"}` (Loki) muncul.

### 5. Impor dashboard

Grafana Cloud → **Dashboards → New → Import** → unggah `grafana/hari-ibadah.json`. Setelah terbuka, pilih datasource Prometheus dan Loki milik stack di dropdown bagian atas, lalu simpan.

Sebagian panel aplikasi (request per status, p95, 429, hasil check-in) baru terisi setelah versi aplikasi dengan log JSON (`kp.request`, dan lainnya) ter-deploy. Panel host dan nginx langsung terisi.

### 6. Pemantau uptime + uji alarm

Ikuti `docs/v3/runbooks/uptime-monitoring.md`. Uji alarmnya (mematikan `faceid` selama beberapa menit) **hanya di hari kerja malam**, tidak pernah Sabtu 15:00–19:00.

### 7. Runbook hari ibadah

Kirim tautan `docs/v3/runbooks/hari-ibadah.md` ke PJ teknis tiap Sabtu. Isi dulu bagian tautan di atasnya.

## Manual vs otomatis

| Hal | Siapa |
|---|---|
| Menyalin berkas ke VPS, menjalankan tiap langkah di atas | Jose, manual |
| Menyunting blok server nginx | Jose, manual (`nginx -t` dulu) |
| Mengisi kredensial Grafana Cloud | Jose, manual (berkas mode 600, tidak pernah masuk git) |
| Membuat monitor Sentry/UptimeRobot dan menguji alarm | Jose, manual di web |
| Rotasi dan penghapusan log lama | Otomatis (journald, logrotate) |
| Pengiriman metrik dan log ke Grafana Cloud | Otomatis (Alloy, setelah langkah 4) |
| Pengecekan `/health` setiap menit dan alarm | Otomatis (setelah langkah 6) |
| Pengumpulan bukti insiden | Manual: `collect_incident.sh` di malam hari setelah kejadian |

## Keamanan

- `collect_incident.sh` tidak membaca `.env`, tidak mengambil `Environment=` milik unit, dan menyaring semua keluarannya: nilai di belakang nama yang mengandung KEY, TOKEN, SECRET, PASSWORD, atau DSN, kredensial di URL, dan token Bearer diganti `[REDACTED]`.
- Tidak ada skrip di sini yang me-restart `faceid`. Yang di-restart atau di-reload hanya journald (langkah 2), nginx (langkah 3, reload tanpa memutus koneksi), dan Alloy (langkah 4).
- Alloy dibatasi `MemoryMax=200M` dan `OOMScoreAdjust=500`. Kalau memori server habis, yang dikorbankan lebih dulu adalah monitoring, bukan absensi.
