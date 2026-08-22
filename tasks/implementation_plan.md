# 📸 Final Execution Plan: Nusantara Festive Light Photobooth Kiosk (KP Bromo)

Dokumen persyaratan lengkap telah dibuat di [`tasks/PHOTOBOOTH_PRD.md`](file:///Users/josetaneo/Private_Coding/faceID-KP/tasks/PHOTOBOOTH_PRD.md).

---

## 🎨 1. Nusantara Festive Light Design System

### A. Palet Warna & Tekstur
* **Background Utama:** Warm Textured Paper `#FAF7F2` (Ivory Alami).
* **Warna Teks Utama:** Charcoal Ink `#1E1B18` (Kontras Tinggi WCAG AAA).
* **Aksen Keberagaman Budaya:**
  * 🔴 **Merah Kemerdekaan:** `#DC2626`
  * 🟤 **Terracotta Tenun:** `#C2410C`
  * 🟡 **Ochre Gold Nusantara:** `#D97706`
  * 🔵 **Royal Indigo Bahari:** `#1E3A8A`
* **Elemen Tactile:** Border `2.5px solid #1E1B18`, Solid Drop Shadow `shadow-[4px_4px_0px_#1E1B18]`, dan stiker miring bertekstur.

---

## 🔄 2. Layar & Alur Interaksi (User Experience)

### Step 1: Layar Awal & Pemilihan Layout (Welcome Screen)
* Tampilan cerah, hangat, dan minimalis.
* Pengguna memilih salah satu dari 4 format layout foto:
  1. **3-Strip Vertikal** (3 Pose — Paling Populer)
  2. **4-Strip Vertikal** (4 Pose — Klasik Studio)
  3. **2x2 Bento Grid** (4 Pose — Kotak Mini)
  4. **Single Wide Polaroid** (1 Pose Lebar — Grup Jemaat)
* Klik **"Mulai Sesi Foto"** langsung mengaktifkan kamera.

### Step 2: Live Viewfinder Bening (Zero Blackout)
* **Kamera 100% Terang & Jernih:** Tidak ada overlay hitam yang menutupi kamera saat hitung mundur.
* Hitung mundur (3s / 5s) tampil sebagai **badge mengambang (*floating pill*)** di atas kamera dengan angka tebal dan suara beep sintetis.
* Flash putih seketika (350ms) + efek suara shutter mekanik saat foto dijepret.
* Jeda 2.5s ganti gaya antar pose.

### Step 3: Dual Output & Animasi Mesin Cetak (*Printer Slide-Out*)
* **Dual Output:**
  * **Static Photo Strip HD (300 DPI):** Format cetak lengkap dengan frame nusantara & stempel 17 Agustus.
  * **Animated Stop-Motion GIF:** Animasi looping berulang dari foto-foto yang baru diambil (menggunakan `gifshot.js` client-side).
* **Animasi Mesin Cetak:** Strip foto meluncur keluar dari slot printer di layar atas dengan bayangan kertas fisik dan efek suara kertas tercetak.

### Step 4: Instant QR Code & Mobile Landing Page
* Layar menampilkan kartu QR Code besar untuk di-scan kamera ponsel.
* Halaman mobile `/p/{id}` memungkinkan jemaat mengunduh file Photo Strip (PNG) **dan** Animated GIF langsung ke galeri ponsel dengan 1-tap.
* Countdown auto-reset 45 detik untuk menjaga alur antrean booth.

---

## 📁 3. Starter Pack Aset 17an (`frontend/assets/photobooth/`)
* `stickers/` : `lencana-dirgahayu.svg`, `pita-merah-putih.svg`, `bintang-nusantara.svg`, `stempel-17an.svg`.
* `frames/` : `batik-kawung-corner.svg`, `tenun-motif-border.svg`.
* Pengguna dapat menambahkan berkas PNG transparan custom ke folder ini kapan saja.

---

## 🧪 4. TDD & Quality Gate
* Unit tests API upload static & GIF buffer di `tests/test_photobooth_api.py`.
* Playwright E2E test untuk transisi Welcome Screen &rarr; Layout Selection &rarr; Camera Viewfinder &rarr; Printing Animation &rarr; QR Modal di `tests/test_e2e_playwright.py`.
* Verifikasi 100% bebas dari unicode emoji mentah.
