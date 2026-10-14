#!/usr/bin/env bash
# Memasang Grafana Alloy di VPS (Ubuntu 24.04) untuk mengirim metrik host dan
# log aplikasi ke Grafana Cloud free tier. Jalankan dari folder scripts/ops:
#
#   sudo bash setup_alloy.sh
#
# Aman diulang: yang sudah terpasang dilewati, konfigurasi diperbarui, dan
# berkas kredensial yang sudah diisi TIDAK PERNAH ditimpa.
#
# Yang dilakukan:
#   1. Menambah repo apt resmi Grafana dan memasang paket `alloy`
#      (perintah persis dari https://grafana.com/docs/alloy/latest/set-up/install/linux/).
#   2. Memasukkan user `alloy` ke grup adm dan systemd-journal, supaya bisa
#      membaca journal dan log nginx (syarat dari dokumentasi loki.source.journal).
#   3. Menyalin alloy/config.alloy ke /etc/alloy/config.alloy (yang lama dicadangkan).
#   4. Membuat /etc/alloy/grafana-cloud.env berisi PLACEHOLDER, mode 600 root.
#   5. Memasang drop-in systemd: membaca berkas env itu dan MEMBATASI memori Alloy.
#   6. Mengaktifkan layanan; baru DIJALANKAN kalau placeholder sudah diganti.
#
# Soal memori: VPS ini 2 GB dan model wajah InsightFace sudah memakan sebagian
# besarnya. Alloy tidak boleh ikut berebut. Karena itu:
#   - MemoryMax=200M: batas keras cgroup. Kalau Alloy melewatinya, yang dibunuh
#     kernel adalah Alloy, bukan aplikasi absensi.
#   - MemoryHigh=160M: di atas ini kernel mulai menekan Alloy lebih dulu.
#   - Alloy otomatis menyetel GOMEMLIMIT ke 90% batas cgroup, jadi garbage
#     collector Go sudah bekerja keras sebelum menyentuh batas
#     (https://grafana.com/docs/alloy/latest/reference/cli/environment-variables/).
#   - OOMScoreAdjust=500: kalau seluruh host kehabisan memori, OOM killer memilih
#     Alloy lebih dulu daripada faceid. Monitoring yang mati jauh lebih murah
#     daripada kiosk yang mati.
#   - CPUWeight/IOWeight rendah: Alloy mengalah saat CPU/disk sibuk.
# Pemakaian normal Alloy dengan konfigurasi sekecil ini diperkirakan jauh di
# bawah 200M; cek setelah sehari dengan `systemctl status alloy` (baris Memory).
# Kalau ternyata sering mentok, naikkan ke 250M — jangan hapus batasnya.
#
# Skrip ini TIDAK menyentuh faceid, nginx, maupun .env aplikasi.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Jalankan dengan sudo: sudo bash $0" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_CONFIG="$SCRIPT_DIR/alloy/config.alloy"
ENV_FILE="/etc/alloy/grafana-cloud.env"
DROPIN_DIR="/etc/systemd/system/alloy.service.d"
DROPIN="$DROPIN_DIR/10-kp.conf"

if [ ! -f "$SRC_CONFIG" ]; then
  echo "Tidak menemukan $SRC_CONFIG. Jalankan dari salinan repo yang utuh (folder scripts/ops)." >&2
  exit 1
fi

if ! grep -q 'VERSION_ID="24.04"' /etc/os-release 2>/dev/null; then
  echo "Peringatan: skrip ini diuji untuk Ubuntu 24.04. Lanjut dalam 5 detik (Ctrl+C untuk batal)..."
  sleep 5
fi

# --- 1. Repo resmi Grafana + paket alloy ------------------------------------
if ! command -v alloy > /dev/null 2>&1; then
  echo "==> Memasang Grafana Alloy dari repo apt resmi Grafana..."
  apt-get update -qq
  apt-get install -y -qq ca-certificates wget
  mkdir -p /etc/apt/keyrings
  wget -q -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
  chmod 644 /etc/apt/keyrings/grafana.asc
  echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" \
    > /etc/apt/sources.list.d/grafana.list
  apt-get update -qq
  apt-get install -y -qq alloy
else
  echo "OK: Alloy sudah terpasang: $(alloy --version 2>/dev/null | head -n 1)"
fi

# --- 2. Izin baca journal dan log nginx -------------------------------------
usermod -aG adm,systemd-journal alloy
echo "OK: User alloy ada di grup: $(id -nG alloy)"

# --- 3. Konfigurasi ----------------------------------------------------------
mkdir -p /etc/alloy
if [ -f /etc/alloy/config.alloy ] && ! cmp -s "$SRC_CONFIG" /etc/alloy/config.alloy; then
  BACKUP="/etc/alloy/config.alloy.bak-$(date +%Y%m%d-%H%M%S)"
  cp /etc/alloy/config.alloy "$BACKUP"
  echo "OK: Konfigurasi lama dicadangkan ke $BACKUP"
fi
install -m 644 "$SRC_CONFIG" /etc/alloy/config.alloy
echo "OK: /etc/alloy/config.alloy diperbarui"

# `alloy validate` hanya ada di versi yang cukup baru; `alloy fmt` minimal
# memastikan sintaksnya bisa dibaca. Konfigurasi rusak tidak boleh sampai
# di-restart — layanan lama yang jalan lebih baik daripada layanan mati.
if alloy validate --help > /dev/null 2>&1; then
  alloy validate /etc/alloy/config.alloy
else
  alloy fmt /etc/alloy/config.alloy > /dev/null
fi
echo "OK: Konfigurasi lolos validasi"

# --- 4. Berkas kredensial (template) ----------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  umask 077
  cat > "$ENV_FILE" <<'EOF'
# Kredensial Grafana Cloud untuk Alloy. Dibaca systemd (sebagai root) lewat
# /etc/systemd/system/alloy.service.d/10-kp.conf, lalu diteruskan ke Alloy
# sebagai environment. Mode 600 root: user lain di server tidak bisa membacanya.
# JANGAN salin berkas ini ke repo.
#
# Cara mengisi (portal Grafana Cloud -> stack Anda):
#   Prometheus -> Details: "Remote Write Endpoint" dan "Username / Instance ID"
#   Loki       -> Details: URL (tambahkan /loki/api/v1/push) dan "User"
#   Administration -> Cloud access policies: buat policy dengan scope
#     metrics:write dan logs:write saja, lalu "Add token". Satu token untuk keduanya.

GCLOUD_PROM_URL=ISI_REMOTE_WRITE_URL_misalnya_https://prometheus-prod-XX-prod-ap-southeast-1.grafana.net/api/prom/push
GCLOUD_PROM_USER=ISI_INSTANCE_ID_PROMETHEUS
GCLOUD_LOKI_URL=ISI_URL_LOKI_misalnya_https://logs-prod-XXX.grafana.net/loki/api/v1/push
GCLOUD_LOKI_USER=ISI_USER_LOKI
GCLOUD_RW_TOKEN=ISI_TOKEN_ACCESS_POLICY
EOF
  chown root:root "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "OK: Template kredensial dibuat: $ENV_FILE (mode 600)"
else
  chmod 600 "$ENV_FILE"
  echo "OK: $ENV_FILE sudah ada, tidak disentuh"
fi

# --- 5. Drop-in systemd ------------------------------------------------------
mkdir -p "$DROPIN_DIR"
cat > "$DROPIN" <<EOF
# Dipasang oleh scripts/ops/setup_alloy.sh. Alasan tiap baris ada di skrip itu.
[Service]
EnvironmentFile=$ENV_FILE
MemoryHigh=160M
MemoryMax=200M
OOMScoreAdjust=500
CPUWeight=20
IOWeight=20
EOF
systemctl daemon-reload
echo "OK: Drop-in systemd dipasang: $DROPIN"

# --- 6. Aktifkan, dan jalankan hanya kalau kredensial sudah diisi -------------
systemctl enable alloy > /dev/null 2>&1
if grep -q '=ISI_' "$ENV_FILE"; then
  systemctl stop alloy > /dev/null 2>&1 || true
  cat <<EOF

Alloy terpasang tapi BELUM dijalankan: $ENV_FILE masih berisi placeholder.

Langkah berikutnya:
  1. sudo nano $ENV_FILE        # isi kelima nilai (petunjuk ada di dalam berkas)
  2. sudo systemctl restart alloy
  3. systemctl status alloy --no-pager        # harus active (running), lihat baris Memory
  4. sudo journalctl -u alloy -n 50 --no-pager # tidak boleh ada "401", "403", atau "permission denied"
  5. Di Grafana Cloud -> Explore:
       Prometheus:  node_memory_MemAvailable_bytes
       Loki:        {job="faceid"}
     Keduanya harus muncul dalam 1-2 menit.
  6. Impor dashboard: scripts/ops/grafana/hari-ibadah.json

UI debug Alloy hanya mendengar di 127.0.0.1:12345. Untuk melihatnya dari laptop:
  ssh -L 12345:127.0.0.1:12345 <user>@<ip-vps>   lalu buka http://localhost:12345
EOF
else
  systemctl restart alloy
  sleep 3
  systemctl --no-pager --lines=0 status alloy || true
  echo
  echo "Cek log: sudo journalctl -u alloy -n 50 --no-pager"
  echo "Lalu impor scripts/ops/grafana/hari-ibadah.json ke Grafana Cloud."
fi
