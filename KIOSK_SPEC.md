# 📱 Spesifikasi UI & Alur Kiosk: FaceID Attendance & Registration Ecosystem

> **Project:** KP Bromo Web (FaceID-KP)  
> **Target Penggunaan:** Terminal Absensi Mandiri di Pintu Masuk Ibadah Pemuda (Sabtu 17:00 WIB, Jl. Bromo 24 Malang)  
> **Kapasitas:** 70–100 Jemaat per ibadah (Alur cepat 16:30–17:15 WIB)  
> **Design System:** Fluid Clarity (Deep Obsidian `#06070A`, Electric Azure `#2563EB`, Luminous Cyan `#38BDF8`, Emerald `#10B981`, Rose `#F43F5E`)  
> **Standar Visual:** Anti-AI Slop, Zero Emojis in UI, Stroke-aligned SVG Icons, High WCAG Contrast.

---

## 🗺️ 1. Peta Layar & Status Kiosk (Architecture Overview)

```
                       ┌───────────────────────────────────────────────┐
                       │        Layar 1: Main Kiosk Scanning           │
                       │    (Camera Oval Viewfinder + Status Panel)    │
                       └───────┬───────────────┬───────────────┬───────┘
                               │               │               │
            [Wajah Terdeteksi] │  [Gagal/Silau]│   [Jemaat Baru]
                               ▼               ▼               ▼
┌────────────────────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│      Layar 2: Success State    │ │ Layar 3: Manual  │ │ Layar 4: Daftar  │
│ (Streak + Emerald Auto-Dismiss)│ │ Fallback Modal   │ │ Anggota Baru     │
└────────────────────────────────┘ └──────────────────┘ └──────────────────┘
```

---

## 🖥️ 2. Layar Utama Kiosk (Idle & Active Scanning State)

### A. Top Navigation Bar:
* **Kiri:** Logo Monogram Waveform `KP BROMO` (*Teks Plus Jakarta Sans Bold*).
* **Kanan (Aksi Cepat):**
  1. Tombol `Jemaat Baru? Daftar Wajah` (*Pill Button Electric Azure #2563EB*).
  2. Tombol `Special Event: KP45 Photobooth` (*Pill Button Gradient Rose/Red #F43F5E* dengan ikon kamera).

### B. Viewfinder Kamera (Lebar 65%):
* **Latar Belakang:** Feed video kamera responsif bersudut melengkung (`rounded-3xl`).
* **Oval Face Guide:** Bingkai penargetan wajah oval berpendar *Luminous Cyan* (`#38BDF8`) dengan target bracket sudut `[ ]`.
* **Animasi Laser Scanline:** Garis horizontal cyan bergerak dinamis naik-turun dalam oval saat memindai.
* **Floating Badge:** Kapsul instruksi di bawah oval: *"Posisikan wajah Anda di dalam lingkaran oval"*.
* **Metadata Overlay:** Teks halus di pojok atas: `Ibadah Sabtu 17:00 WIB • Jl. Bromo 24 Malang`.

### C. Panel Telemetri & Status (Lebar 35%):
* **Jam Digital Real-time:** Format `16:48:22 WIB` (*Font JetBrains Mono*).
* **Kartu Status Presensi:**
  * Judul: *"Siap Presensi Ibadah"*.
  * Sub-judul: *"Berdiri tegak menghadap kamera untuk scan otomatis"*.
  * Progress Bar: Animasi gradient Azure saat wajah mulai terdeteksi.
* **Feed Kehadiran Terakhir (Live Ticker):**
  * Menampilkan 4 jemaat terakhir yang berhasil check-in secara live:
    * Inisial Avatar, Nama Lengkap, Divisi/Komsel (`Divisi Musik`, `Divisi Acara`, `Komsel Barat`, `Jemaat Umum`), dan Timestamp.

### D. Bottom Action Dock:
* **Tombol Utama (Lebar Penuh):** *"Wajah Belum Terdeteksi? Cari Nama Manual (1-Tap Check-in) ➔"* (*Tombol Glassmorphic besar dengan ikon Search*).

---

## 🔍 3. Modal Cari Nama Manual (Fast Autocomplete Fallback)

> **Tujuan:** Mengatasi antrean ketika kamera silau, jemaat mengenakan topi/kacamata tebal, atau wajah belum terdeteksi.

* **Trigger:** Klik tombol *"Cari Nama Manual"* di layar utama.
* **Komponen Modal:**
  1. **Header Modal:**
     * Judul: `Cari Nama Jemaat (Manual Check-in)`.
     * Deskripsi: `Ketik minimal 1 huruf untuk mencari data Anda.`
     * Tombol `✕` Tutup.
  2. **Search Input Bar:**
     * Input autofocus dengan ikon Search: `Ketik nama jemaat...` (*Border Azure saat fokus*).
     * Debounce 300ms untuk pencarian responsif dan instan.
  3. **Daftar Hasil Pencarian (Live Results):**
     * Item Kartu Jemaat:
       * Avatar & Inisial.
       * Nama Lengkap & Gender (`L / P`).
       * Tag Divisi / Komsel (*Badge JetBrains Mono*).
       * Tombol Aksi 1-Tap: `Check-in Hadir ✓` (*Hijau Emerald #10B981*).
  4. **State Jika Nama Tidak Ditemukan:**
     * Pesan: *"Nama tidak ditemukan. Belum pernah terdaftar?"*
     * Tombol Direct: `+ Daftarkan Diri Sebagai Jemaat Baru ➔`.

---

## 📝 4. Modal Pendaftaran Jemaat Baru (New Member Registration)

> **Tujuan:** Onboarding cepat untuk jemaat baru atau pemuda yang belum mendaftarkan wajahnya ke sistem.

* **Trigger:** Klik tombol *"Jemaat Baru? Daftar Wajah"* di top bar.
* **Langkah 1: Formulir Identitas Singkat (Quick Form)**
  * **Nama Lengkap:** Input teks (wajib).
  * **Jenis Kelamin:** Pilihan Radio Pill (`Pria` / `Wanita`).
  * **Kategori / Divisi Pelayanan:** Dropdown pilihan (`Jemaat Umum`, `Divisi Musik`, `Divisi Acara`, `Divisi Media`, `Divisi Pemerhati`, `Divisi Sarpras`, `Komsel Pemuda`).
  * **Nomor WhatsApp:** Input nomor (opsional/untuk follow-up tim Pemerhati).
* **Langkah 2: Pengambilan Foto Wajah (Face Capture)**
  * Mini camera viewfinder interaktif.
  * Indikator kualitas pencahayaan (*"Wajah terlihat jelas & tegak"*).
  * Tombol `Ambil Foto Wajah` (Auto extract embedding MediaPipe 128/512-dimensi).
* **Langkah 3: Konfirmasi & Langsung Presensi**
  * Tombol `Simpan & Langsung Check-in Hari Ini ➔`.

---

## 🟢 5. Layar Status Berhasil (Check-in Success State)

* **Tampilan:** Glassmorphic Success Card menutupi panel status dengan animasi fade-in halus.
* **Elemen UI:**
  1. **Badge Ikon Sukses:** Lingkaran hijau pendar dengan ikon Checkmark SVG besar.
  2. **Sapaan Personal:** *"Halo, Jonathan Setiawan!"* (*Plus Jakarta Sans 24px Bold*).
  3. **Sub-teks:** *"Presensi Ibadah Pemuda Berhasil Dicatat"*.
  4. **Badge Verifikasi:** `Face ID Verified • 16:48 WIB` (*JetBrains Mono*).
  5. **Kotak Notifikasi Streak:**
     * `🔥 4x Hadir Berturut-turut` (*Badge Emerald*).
     * `Terakhir Hadir: Sabtu Lalu • Divisi Musik`.
  6. **Countdown Auto-Dismiss Bar:**
     * Bar progress hijau yang menyusut dari 100% ke 0% dalam 3.5 detik.
     * Label: `Kembali ke layar scan dalam 3 detik...`.
     * Efek: Otomatis kembali ke layar scan tanpa perlu menyentuh layar.

---

## 🔴 6. Layar Status Gagal / Belum Terdeteksi (Unrecognized State)

* **Tampilan:** Kartu Glassmorphic Peringatan Amber dengan viewfinder berbingkai warning ring.
* **Elemen UI:**
  1. **Badge Ikon Peringatan:** Ikon tanda seru/warning dalam lingkaran *Amber Glass #F59E0B*.
  2. **Judul:** *"Wajah Belum Terdeteksi"*.
  3. **Penjelasan Ramah:** *"Sistem belum mengenali wajah Anda. Pastikan pencahayaan cukup atau gunakan pencarian manual."*
  4. **2 Tombol Aksi Langsung:**
     * **Tombol Primer:** `Cari Nama Manual (1-Tap Check-in) ➔` (*Electric Azure #2563EB*).
     * **Tombol Sekunder:** `Coba Pindai Ulang` (*Ghost Outline dengan ikon refresh*).
  5. **Link Bawah:** *"Belum terdaftar sebagai anggota? Daftar Wajah Baru di Sini"*.

---

## 🔊 7. Spesifikasi Audio & Interaksi Taktil (Feedback Signals)

* **Audio Sukses:** *Short Dual Chime* (Frekuensi nada 520Hz & 680Hz harmonis, ~180ms).
* **Audio Warning/Gagal:** *Soft Low Double Beep* (Frekuensi 320Hz, ~150ms).
* **Animasi Tekan Tombol:** `active:scale-[0.98]` dengan transisi `0.15s ease-out`.

---

## ✍️ 8. Prompt Siap Pakai untuk Stitch (Text-to-UI)

### 🔹 Prompt Kiosk: Manual Fallback Search Modal
```text
A high-tech, dark glassmorphic 'Manual Search Fallback Modal' for Komisi Pemuda GKI Bromo FaceID Kiosk, adhering to the 'Fluid Clarity' Deep Obsidian (#06070A) design system. 

Layout:
- Centered elevated glass modal on top of a dimmed camera viewfinder.
- Top: Title 'Cari Nama Jemaat (Manual Check-in)' with subtitle 'Ketik minimal 1 huruf untuk mencari data Anda' and a close button.
- Search Input: Large, autofocus search bar with search icon and Azure focus ring.
- Live Search Results List: 3 attendee cards showing avatar initials, Full Name, Gender, Division pill ('Divisi Musik', 'Komsel Barat'), and a prominent Emerald green 'Check-in Hadir ✓' button.
- Bottom Empty State: Subtle card 'Nama tidak ditemukan? Daftarkan Jemaat Baru →'.

Styling: Deep Obsidian (#06070A) surface, hairline borders (rgba(255,255,255,0.08)), Plus Jakarta Sans typography, JetBrains Mono tags, crisp SVG icons, high WCAG contrast, no emojis.
```

### 🔹 Prompt Kiosk: New Member Registration Modal
```text
A streamlined, high-tech 'New Member Face Registration Modal' for church youth ministry (Komisi Pemuda GKI Bromo), designed in the 'Fluid Clarity' Deep Obsidian (#06070A) theme. 

Layout:
- Glassmorphic modal with 2-column or step-by-step layout:
  - Left column (Form): Full Name input, Gender pill selector (Pria / Wanita), Ministry Division dropdown (Divisi Musik, Acara, Media, Komsel, Jemaat Umum), and WhatsApp number input.
  - Right column (Face Capture): Live mini camera viewfinder with an oval face guideline, lighting check badge ('Pencahayaan Baik'), and a 'Capture Face Embedding' button with camera icon.
- Bottom CTA: Large Electric Azure (#2563EB) button 'Simpan & Langsung Presensi Hari Ini →'.

Styling: Deep Obsidian (#06070A) background, hairline 1px borders, Plus Jakarta Sans headers, JetBrains Mono metadata, stroke-aligned SVG icons, zero generic emojis.
```
