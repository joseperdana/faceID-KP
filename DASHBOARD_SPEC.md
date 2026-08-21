# 📊 Spesifikasi UI & Data Dashboard: KP Bromo Attendance Intelligence Hub

> **Project:** KP Bromo Web (FaceID-KP)  
> **Target Pengguna:** 34 Pengurus Komisi Pemuda GKI Bromo & Tim Pemerhati (Care Ministry)  
> **Design System:** Fluid Clarity (Deep Obsidian `#06070A`, Electric Azure `#2563EB`, Luminous Cyan `#38BDF8`)  
> **Standar Visual:** Anti-AI Slop, Zero Emojis in UI, Stroke-aligned SVG Icons, High WCAG Contrast.

---

## 🧭 1. Navigasi & Header Global

### A. Sidebar Navigasi (Kiri):
* **Brand Header:**
  * Logo Monogram: `KP BROMO` Waveform Monogram
  * Sub-label: `Leader Portal` (Badge font *JetBrains Mono*)
* **Menu Items:**
  1. `Overview / Ringkasan`: Halaman utama metrik real-time & overview ibadah.
  2. `Live Attendance`: Monitoring arus masuk jemaat secara live saat ibadah (16:30–17:15 WIB).
  3. `Direktori Jemaat`: Database jemaat, status aktif/non-aktif, & update foto wajah.
  4. `Pemerhati & At-Risk`: Modul khusus tim Pemerhati untuk jemaat yang absen >3 minggu.
  5. `KP45 Photobooth Logs`: Galeri foto dan download history jemaat dari photobooth.
  6. `Pengaturan & Akun`: Manajemen password admin, geofencing threshold, & hak akses.
* **Footer Sidebar:**
  * Profil Pengurus aktif (Avatar, Nama Pengurus, Role/Divisi).
  * Tombol `Logout` (Glassmorphic hover red).

### B. Top Action Bar:
* **Konteks Ibadah:** `Youth Attendance Intelligence` • `Sabtu, 21 Agustus 2026 • Ibadah 17:00 WIB`.
* **Filter Waktu:** Dropdown rentang waktu (`Hari Ini`, `Bulan Ini`, `Semester Ini`, `Custom Date`).
* **Tombol Aksi Cepat:**
  * Tombol `Export Excel / CSV` (Ghost glass dengan ikon download).
  * Tombol `+ Daftarkan Jemaat Baru` (*Electric Azure #2563EB* pill button).

---

## 📈 2. Baris Kartu KPI Utama (4 Top Stat Cards)

1. **Card 1: Total Kehadiran Hari Ini**
   * **Angka Metrik:** `84` / Target `100` Jemaat (*JetBrains Mono 32px Bold*).
   * **Badge Pertumbuhan:** `+14% vs minggu lalu` (*Emerald Green #10B981*).
   * **Sub-info:** `Puncak kedatangan: 16:52 WIB`.

2. **Card 2: Rasio Metode Presensi**
   * **Visual:** Split progress bar dual-color (*Azure vs Slate*).
   * **Rincian Data:**
     * Face Scan: `72 (86%)`
     * Manual Fallback: `12 (14%)`
   * **Tujuan:** Mengukur efektivitas scan wajah kiosk vs pencarian manual.

3. **Card 3: Jemaat Baru (First-Timers)**
   * **Angka Metrik:** `6 Jiwa Baru` (*JetBrains Mono*).
   * **Status Follow-up:** `4 Sudah Dihubungi` • `2 Menunggu Follow-up`.
   * **Badge Tag:** *Luminous Cyan #38BDF8*.

4. **Card 4: Jemaat At-Risk (Perlu Perhatian Pemerhati)**
   * **Angka Metrik:** `7 Jemaat` (*JetBrains Mono*).
   * **Kriteria:** Tidak hadir $\ge 3$ minggu berturut-turut.
   * **Badge Status:** *Amber Warning #F59E0B* + Tombol cepat `Buka Daftar Care ➔`.

---

## 📊 3. Visualisasi Grafik & Demografi (Middle Row)

### A. Grafik Tren Kehadiran Mingguan (Lebar 60%):
* **Tipe Visual:** *Smooth Area Line Chart* dengan gradient *Electric Azure* ke transparan.
* **Sumbu X:** Tanggal ibadah Sabtu (8 minggu terakhir).
* **Sumbu Y:** Jumlah jemaat hadir (0 – 120).
* **Fitur Tambahan:** Pin penanda event khusus (misal: *KP45 Special Event*, *Ibadah Gabungan*, *Ret-ret Pemuda*).

### B. Distribusi Divisi Pelayanan & Gender (Lebar 40%):
* **Distribusi Divisi:** Bar horizontal persentase kehadiran:
  * `Divisi Musik / Worship`: 95% (19/20)
  * `Divisi Acara & Liturgis`: 90% (9/10)
  * `Divisi Media & Kreatif`: 100% (6/6)
  * `Komsel / Cell Groups`: 78% (35/45)
  * `Jemaat Umum`: 82%
* **Rasio Gender:** Donut chart `Pria: 48%` vs `Wanita: 52%`.

---

## 📋 4. Tabel Data Utama: Roster Kehadiran & Aksi Tindak Lanjut

**Judul Tabel:** `Daftar Hadir Ibadah Hari Ini & Pastoral Care`  
**Fitur:** Live search bar input nama, dropdown filter divisi, status filter (`Semua`, `Hadir`, `At-Risk`).

| Kolom | Tipe UI | Format Data |
| :--- | :--- | :--- |
| **Jemaat** | Avatar + Nama Lengkap + Gender | `[Foto] Jonathan Setiawan (L)` |
| **Kategori / Divisi** | Badge Kapsul | `Divisi Musik`, `Divisi Acara`, `Komsel Barat`, dll. |
| **Waktu Presensi** | Text Mono | `16:48:12 WIB` (*JetBrains Mono*) |
| **Metode Check-in** | Pill Badge | `Face ID` (*Cyan*) / `Manual` (*Slate*) |
| **Streak Kehadiran** | Badge Counter | `5x Hadir` (*Emerald*) / `1st Time` (*Cyan*) |
| **Status Pastoral** | Status Indicator | `Hadir`, `Izin/Sakit`, `At-Risk (>3 Mgg Absen)` |
| **Aksi Cepat** | Action Button | **1-Click `Kirim WA Care`** (buka `wa.me/62...`) + `Edit` |

---

## 📸 5. Widget Tambahan: KP45 Photobooth Live Feed (Card / Sidebar)

* **Thumbnail Grid:** 3 snapshot foto terbaru yang dicetak jemaat di booth.
* **Counter:** `42 Foto Dicetak Hari Ini`.
* **Aksi:** Link `Buka Galeri Photobooth ➔`.

---

## ✍️ 6. Prompt Siap Pakai untuk Stitch (Text-to-UI)

```text
A high-density, professional Admin Attendance Intelligence Dashboard for Komisi Pemuda GKI Bromo Malang church leaders, strictly following the 'Fluid Clarity' Deep Obsidian (#06070A) design system. 

Layout & Components:
1. Left glassmorphic sidebar with 'KP BROMO Leader Portal' fluid monogram logo, and navigation items (Overview, Live Attendance, Direktori Jemaat, Pemerhati & At-Risk, KP45 Photobooth Gallery, Settings).
2. Top action bar with title 'Attendance Intelligence Hub', Saturday worship date filter, 'Export Excel/CSV' outline button, and '+ Daftarkan Jemaat' azure pill button.
3. 4 top KPI stat cards:
   - Card 1: 'Total Kehadiran Hari Ini' (84/100 in JetBrains Mono with +14% emerald badge).
   - Card 2: 'Metode Presensi' (Face Scan 72 (86%) vs Manual 12 (14%) progress bar).
   - Card 3: 'Jemaat Baru' (6 Jiwa with 4 Followed-up cyan badge).
   - Card 4: 'Perlu Follow-up (At-Risk)' (7 Jemaat in amber warning badge for >3 weeks absent).
4. Middle analytics row: Weekly attendance smooth area line chart (60% width) and division/gender distribution breakdown (40% width).
5. Comprehensive bottom data table 'Daftar Hadir Ibadah Hari Ini & Pastoral Care' with avatar, name, division badge, check-in time in JetBrains Mono, method badge (Face Scan / Manual Tag), streak counter (e.g. 5x Hadir), and a 1-click 'WhatsApp Care' action button for youth ministry follow-up.

Styling: Deep Obsidian (#06070A) canvas, hairline 1px translucent borders (rgba(255,255,255,0.08)), Plus Jakarta Sans headings, JetBrains Mono metrics, crisp stroke SVG line icons, zero generic emojis, high WCAG contrast.
```
