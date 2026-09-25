# Post-mortem: layanan absensi macet saat Gibbor 2026

**Status:** Draf. Penyebab utama sudah sangat mungkin, kronologi dari sisi panitia belum lengkap.
**Tanggal kejadian:** Sabtu, 19 September 2026, sekitar 17:00–17:45 WIB
**Ditulis:** 26 September 2026 · Jose Taneo
**Format:** blameless. Dokumen ini mencari *apa* yang gagal dan *kenapa sistem membiarkannya gagal*, bukan *siapa*.

Bagian bertanda `[ISI: ...]` belum diisi.

---

## Ringkasan

Pada acara Gibbor, Sabtu 19 September 2026, kiosk absensi dan form Lark terasa tidak bisa diakses sekitar pukul 17:00–17:45 WIB. Gangguan terparah terjadi pukul **17:19–17:27**, bersamaan dengan gelombang pendaftaran anggota baru.

Servernya **tidak mati**. Prosesnya tetap hidup sepanjang acara (`NRestarts=0`), tetapi **membeku**. Aplikasi berjalan sebagai satu proses uvicorn, dan beberapa handler `async` (terutama `/api/register`) memanggil Supabase secara sinkron langsung di event loop. Selama satu panggilan itu menunggu, **seluruh** request lain ikut berhenti, termasuk halaman kiosk dan file JavaScript statis. Pada saat yang sama koneksi HTTP/2 bersama ke Supabase terputus (`RemoteProtocolError: ConnectionTerminated`), sehingga panggilan yang menggantung bisa tertahan lama. Nginx akhirnya membalas **504** setelah 60 detik, dan banyak pengguna menyerah lebih dulu (**499**).

Dugaan awal soal rate limit per IP (H2) **terbantah**: tidak ada satu pun 429, dan perangkat panitia ternyata memakai data seluler masing-masing.

## Dampak

Dari log akses nginx, jendela 16:00–18:59 WIB:

| Status | Jumlah | Arti |
|---|---|---|
| 200 | 1159 | Berhasil |
| 304 | 571 | Berhasil (cache) |
| 400 | 321 | Ditolak aplikasi. **309 di antaranya dari `/api/register`**, alasannya belum bisa dipilah (lihat "Belum terjawab") |
| 499 | 82 | Pengguna menyerah sebelum dijawab |
| 404 | 69 | |
| **504** | **54** | Aplikasi tidak menjawab dalam 60 detik |
| 303 | 21 | |
| 500 | 5 | Error aplikasi |
| 408 | 5 | |
| 429 | **0** | Tidak ada rate limit yang terpicu |

Path yang paling terdampak:
- `/api/register`: 29×504, 27×499, 1×500 (plus 309×400)
- `/` (halaman kiosk itu sendiri): 24×499
- `/api/recognize`: 21×504, 13×499, 1×500 (plus 8×400)
- `/api/update-face`: 2×504, 3×499 · `/api/attendance/manual-checkin`: 2×504 · `/api/users/search`: 3×500
- Bahkan `/static/js/*.js` ikut mendapat 499

Dampak ke orang:
- Jumlah peserta yang terpaksa absen di kertas atau tidak tercatat: `[ISI: dari panitia]`
- Jumlah pendaftar baru yang gagal dan harus diulang: `[ISI]`
- Durasi gangguan yang dirasakan panitia: `[ISI: dari chat panitia]`

## Kronologi (WIB)

| Waktu | Kejadian | Sumber |
|---|---|---|
| `[ISI]` | Kiosk mulai dipakai, jumlah perangkat `[ISI]` | panitia |
| 16:55–16:56 | Lonjakan kecil pertama: beberapa 504 dan 4×499 | nginx |
| `[ISI]` | Laporan pertama "kiosk lambat/tidak bisa" | chat panitia |
| 17:19 | Gangguan utama dimulai: 18×499 + 8×504 dalam satu menit | nginx |
| 17:20:00 | `POST /api/register` → 500, disusul `httpx.RemoteProtocolError: <ConnectionTerminated error_code:1, last_stream_id:31>` | journal faceid |
| 17:22 | `Exception in ASGI application` berulang | journal faceid |
| 17:23 | Puncak: 19×499 + 12×504 + 1×500 dalam satu menit | nginx |
| `[ISI]` | Form Lark dilaporkan tidak terbuka | chat panitia |
| `[ISI]` | Panitia beralih ke `[ISI: kertas / cari manual]` | panitia |
| 17:27 | Gangguan utama mereda, error berhenti | nginx |
| 17:45 | Satu 499 terakhir | nginx |

Sepanjang jendela ini proses tidak pernah restart (`NRestarts=0`), dan log kernel tidak berisi apa pun kecuali satu baris "no entries".

## Data yang tersedia vs hilang

| Tersedia | Hilang, dan akibatnya |
|---|---|
| Log akses nginx 16:00–18:59: status, path, IP klien | **Waktu per request** (`$request_time`, `$upstream_response_time`) tidak dicatat, jadi berapa lama request menggantung hanya bisa diduga dari 504 |
| Journal `faceid`: log teks uvicorn dan traceback | Log terstruktur (route, durasi, perangkat) belum ada. Tahap check-in mana yang lambat tidak terlihat |
| Log kernel: tidak ada OOM | **Metrik host** (RAM, swap, PSI). Swap berat tanpa OOM tidak bisa dikesampingkan sepenuhnya |
| `systemctl show faceid`: `NRestarts=0`, ExecStart uvicorn tunggal | **Identitas perangkat** per request: kiosk mana yang bermasalah tidak diketahui |
| Kode per commit `HEAD` | **Versi yang berjalan pada 19 Sep**: `[ISI: commit/release dari server atau Sentry]` |
| Issue Sentry: `[ISI: tautan]` | **Jaringan tiap perangkat**: hanya bisa disimpulkan dari rentang IP |
| | **Jam kejadian versi panitia**: belum dikumpulkan dengan presisi |
| | **Alasan 309×400 di `/api/register`** |

Bukti mentah bisa dikumpulkan ulang dan diarsipkan dengan:

```bash
sudo bash scripts/ops/collect_incident.sh --since "2026-09-19 16:00" --until "2026-09-19 19:00"
```

**Kerjakan sebelum sekitar 3 Oktober 2026.** Log nginx di Ubuntu dirotasi harian dan disimpan 14 hari. Setelah tanggal itu, log akses Gibbor hilang untuk selamanya. Simpan tarball-nya di tempat privat (isinya memuat IP dan user_id), catat lokasinya di sini: `[ISI]`.

## Analisis per hipotesis

Hipotesis H1–H4 berasal dari MASTERPLAN §2.1, ditulis sebelum log dibaca. H5 muncul dari log.

### H1 — Kehabisan memori (OOM atau swap) · *tidak didukung; swap belum bisa dikesampingkan*

- **Premis awal keliru.** MASTERPLAN menulis H1 berdasarkan `scripts/deploy_vps.sh`: gunicorn 2 worker, masing-masing memuat model. Produksi ternyata **satu proses uvicorn** di `/home/adminKPBromo/faceID-KP`, jadi hanya ada satu salinan model.
- **Bukti yang dicari:** baris OOM killer di log kernel, proses yang restart, swap-in tinggi.
- **Cara mengambil:** `collect_incident.sh` → `21_kernel_oom_window.txt`, `12_service_lifecycle.txt`, `SUMMARY.txt` bagian H1. Untuk insiden berikutnya: panel RAM, Swap, dan PSI di dashboard "Hari Ibadah".
- **Temuan:** log kernel kosong, `NRestarts=0`. Tidak ada OOM. Apakah server sempat swap berat tidak bisa dijawab karena metrik host belum ada. Meski begitu, swap tidak menjelaskan mengapa file JS statis ikut 499. Event loop yang membeku menjelaskannya.

### H2 — Rate limit per IP di balik satu NAT · *terbantah*

- **Bukti yang dicari:** banyak 429 dari satu IP.
- **Cara mengambil:** `collect_incident.sh` → `53_nginx_top.txt` (IP untuk 429 dan untuk `/api/`), `SUMMARY.txt` bagian H2.
- **Temuan:** **nol 429** di seluruh jendela. IP klien tersebar di rentang operator seluler (182.4.x, 182.5.x, 114.5.x), bukan satu IP Wi-Fi gereja. Uvicorn juga melihat IP klien yang asli, sehingga rate limit per IP bekerja sesuai rancangan.
- **Pertanyaan jaringan** (Wi-Fi gereja atau seluler) sebelumnya dianggap 50:50. Sebaran IP menjawabnya: **sebagian besar perangkat memakai data seluler**. Kesimpulan ini diambil dari rentang IP. `[ISI: konfirmasi ke panitia]`. Mulai sekarang jaringan tiap kiosk dicatat di checklist T-60 (`docs/v3/runbooks/hari-ibadah.md`).

### H3 — Rantai query Supabase berurutan · *relevan, tetapi bukan mekanisme utamanya*

- **Bukti yang dicari:** durasi request per route, durasi per tahap check-in.
- **Cara mengambil:** belum bisa untuk Gibbor, karena waktu per request tidak tercatat. Mulai sekarang ada tiga sumber: format log nginx `kp_timed` (`scripts/ops/nginx-logformat.conf`, dibaca `collect_incident.sh` → `54_nginx_request_time_per_minute.tsv`), `duration_ms` di log `kp.request`, dan `stage_ms` di `kp.checkin`.
- **Temuan:** query berurutan memperpanjang setiap request. Namun di `/api/recognize` semuanya sudah dibungkus `run_in_threadpool`, jadi query itu hanya memperlambat request itu sendiri. Masalah besarnya ada di handler yang **tidak** dibungkus (lihat H5).

### H4 — Masalah di sisi klien atau jaringan venue · *bukan penyebab utama*

- **Bukti yang dicari:** celah tanpa request di log nginx saat layanan tetap hidup.
- **Cara mengambil:** `collect_incident.sh` → `51_nginx_status_per_minute.tsv`, `SUMMARY.txt` bagian H4.
- **Temuan:** request tetap sampai ke nginx sepanjang gangguan. 499 justru membuktikan klien berhasil terhubung lalu menunggu terlalu lama. Halaman kiosk `/` sendiri kena 24×499, artinya server tidak menjawab bahkan untuk halaman HTML. Jadi masalahnya di sisi server.
- **Lark:** form Lark dimuat langsung dari server Lark, tetapi di kiosk ia baru dibuka **setelah** `/api/register` atau `/api/recognize` menjawab. Dugaan kuat: Lark "tidak bisa dibuka" karena kiosk menunggu server kita yang membeku, bukan karena Lark bermasalah. **Belum terbukti.**

### H5 — Event loop membeku oleh panggilan Supabase sinkron, diperparah koneksi HTTP/2 yang putus · *penyebab utama, sangat mungkin*

- **Bukti yang dicari:** error koneksi ke Supabase yang waktunya bertepatan dengan lonjakan 504/499; 504/499 di path yang tidak menyentuh database; proses yang tetap hidup.
- **Cara mengambil:** `collect_incident.sh` → `13_upstream_errors.txt`, `14_upstream_errors_per_minute.tsv`, `52_nginx_errors_per_minute_paths.txt`, `SUMMARY.txt` bagian H5. Untuk insiden berikutnya: panel "Koneksi ke Supabase putus" di dashboard.
- **Temuan dari log:**
  - Journal faceid di jendela: `httpx.RemoteProtocolError` ×7 (termasuk `ConnectionTerminated`), `postgrest APIError` ×6, `httpx.LocalProtocolError` ×3, `KeyError` ×2.
  - Error pertama (17:20:00) jatuh di dalam lonjakan utama 17:19–17:27.
  - 504/499 menimpa hampir semua path, termasuk `/` dan `/static/js/*.js` yang tidak menyentuh database sama sekali. Pola ini khas event loop yang terblokir: satu panggilan yang menggantung menahan semua request lain.
  - `NRestarts=0`: proses hidup terus, tidak crash.
- **Temuan dari kode** (commit `HEAD`, fungsi-fungsinya sama dengan yang berjalan saat itu `[ISI: pastikan dengan versi di server]`):
  - `register_user` dan `update_face` di `routers/kiosk.py` adalah `async def`, tetapi memanggil `DBService.get_user_by_name_key`, `match_faces`, `insert_user`, `insert_log`, `get_user_by_name`, dan `update_user` **langsung**, tanpa `run_in_threadpool`. Selama panggilan itu berjalan, event loop berhenti.
  - Pola yang sama ada di handler dashboard (`routers/users.py`, `routers/attendance.py`, misalnya `/api/all-logs` yang memuat seluruh tabel), dan di `flags.is_enabled` saat cache-nya kosong.
  - Klien sinkron supabase/postgrest memakai **satu `httpx.Client` bersama dengan `http2=True`** dan timeout bawaan 120 detik. Klien itu dipanggil bersamaan dari banyak thread. Saat koneksi HTTP/2-nya diputus (GOAWAY → `ConnectionTerminated`) atau state h2-nya rusak karena dipakai bersamaan (`LocalProtocolError`), panggilan yang sedang berjalan gagal atau menggantung.
  - Dengan satu proses uvicorn, tidak ada worker kedua yang bisa mengambil alih.
- **Pemicu:** gelombang pendaftaran pukul 17:19–17:27. Satu pendaftaran menjalankan InsightFace pada 3 foto resolusi penuh, ditambah 4 panggilan Supabase yang memblokir event loop.

## Penyebab

**Penyebab utama (sangat mungkin):** panggilan Supabase sinkron yang dijalankan langsung di event loop pada satu-satunya proses uvicorn. Saat pendaftaran ramai, setiap panggilan itu menghentikan semua request lain. Ketika koneksi HTTP/2 bersama ke Supabase putus, panggilan yang menggantung bisa tertahan sampai puluhan detik. Nginx lalu membalas 504 setelah 60 detik (`proxy_read_timeout`, `[ISI: pastikan dari 41_nginx_directives.txt]`), dan pengguna yang menyerah tercatat sebagai 499. Dari luar layanan terlihat mati, padahal prosesnya membeku.

**Faktor yang memperbesar dampak:**
- Satu proses, tanpa worker cadangan.
- Timeout klien Supabase 120 detik, jauh di atas batas nginx 60 detik.
- Model mental tim tentang produksi keliru: `scripts/deploy_vps.sh` menggambarkan gunicorn 2 worker di `/var/www`, padahal produksi berbeda. Hipotesis awal (H1) disusun dari gambaran yang salah itu.
- Tidak ada metrik host, timing request, atau pemantau uptime. Diagnosis baru bisa dibuat seminggu kemudian, dari log yang kebetulan belum terhapus.

**Belum terjawab:**
- Alasan 309×400 di `/api/register`: nama duplikat, wajah tidak terdeteksi, atau wajah sudah terdaftar (ambang 0,5). Log sekarang tidak membedakannya.
- Apa yang memicu Supabase memutus koneksi HTTP/2 (batas stream, idle timeout, atau hal lain).
- Apakah swap ikut berperan (butuh metrik host).
- Lonjakan kecil 16:55–16:56: apakah mekanismenya sama.

## Tindakan

| # | Tindakan | Status | Rujukan |
|---|---|---|---|
| 1 | Pindahkan semua panggilan DB sinkron keluar dari event loop, plus tes penjaga yang gagal kalau ada handler `async` memanggil DB langsung | Sedang dikerjakan, branch `feature/v3-f0-observability` | MASTERPLAN §5, §6.2 |
| 2 | Klien Supabase memakai HTTP/1.1, timeout terbatas (di bawah 60 detik nginx), dan retry yang aman | Sedang dikerjakan | §6.2 |
| 3 | Ukuran unggahan pendaftaran diperkecil | Sedang dikerjakan | §6.2 |
| 4 | Log terstruktur `kp.request` / `kp.checkin` / `kp.ratelimit`, **ditambah outcome terstruktur untuk registrasi** (supaya 400 bisa dipilah) | `kp.*` sedang dikerjakan; outcome registrasi `[ISI: belum]` | §5.2 |
| 5 | Arsipkan bukti Gibbor dengan `collect_incident.sh` sebelum sekitar 3 Oktober 2026 | `[ISI]` | §5.1 |
| 6 | Format log nginx `kp_timed` (waktu per request, label perangkat) | Siap pasang: `scripts/ops/nginx-logformat.conf` | §5.2 |
| 7 | Retensi journald 90 hari | Siap pasang: `scripts/ops/journald-retention.conf` | §5.1 |
| 8 | Alloy → Grafana Cloud + dashboard "Hari Ibadah" | Siap pasang: `scripts/ops/setup_alloy.sh`, `scripts/ops/grafana/hari-ibadah.json` | §5.2 |
| 9 | Pemantau uptime `/health` + uji alarm | Runbook: `docs/v3/runbooks/uptime-monitoring.md` | §5.2 |
| 10 | Runbook hari ibadah, termasuk mencatat jam dan jaringan tiap kiosk | Selesai: `docs/v3/runbooks/hari-ibadah.md` | §5 |
| 11 | Samakan `scripts/deploy_vps.sh` dengan produksi (uvicorn tunggal di `/home/adminKPBromo`), atau sebaliknya | Tindak lanjut `[ISI: pemilik]` | §6.2 |
| 12 | Uji beban skenario "ulang Gibbor", **termasuk registrasi massal** | Fase 1 | §6.1 |

## Pelajaran

- **"Down" tidak selalu berarti mati.** Proses yang membeku terlihat sama persis dengan server mati dari HP pengguna. Hanya log yang bisa membedakannya.
- **Hipotesis yang ditulis dari skrip deploy bisa salah kalau produksi berbeda dari skrip itu.** Mulai sekarang, pencatatan kondisi produksi yang sebenarnya (`systemctl show`, ExecStart) ikut direkam di setiap pengumpulan data insiden.
- **Log yang sederhana pun cukup kuat.** Hitungan status nginx menutup H2 dalam hitungan menit. Masalahnya bukan ketiadaan log, melainkan log itu hampir terhapus sebelum sempat dibaca.
- **Jam yang tepat adalah bukti.** Tanpa catatan "17:21 kiosk-03 macet" dari panitia, kronologi disusun dari log server saja, dan pengalaman pengguna tidak ikut tergambar.
