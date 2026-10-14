#!/usr/bin/env bash
# Sekali jalan, Oktober 2026: ganti kredensial yang bocor + deploy Fase 0.
#
# Kenapa digabung jadi satu skrip:
#   - .env lama ikut ter-commit di repo publik (c3b7558d, Februari 2026).
#     ADMIN_PASSWORD di dalamnya masih berlaku, dan server masih memakai kunci
#     anon lama yang sama.
#   - Server menjalankan supabase-py 2.27.3. Versi itu kemungkinan belum
#     mengenal format secret key baru (sb_secret_...), jadi kunci baru dan kode
#     baru (yang memaksa supabase>=2.28) harus naik BERSAMAAN.
#   - Kalau satu langkah gagal, semuanya dikembalikan: .env lama dan commit
#     lama. Kiosk yang jalan dengan kredensial lama lebih baik daripada kiosk
#     yang mati.
#
# Cara pakai (di VPS, bukan hari Sabtu 15:00–19:30):
#   bash rotate_and_deploy.sh
# Skrip akan meminta secret key Supabase baru (tidak tampil di layar), membuat
# password admin baru, dan menampilkannya SEKALI di akhir.
#
# Secret key dibuat dulu di Supabase Dashboard → Project Settings → API Keys →
# Secret keys → "Add new secret key" (beri nama: vps-produksi).

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/faceID-KP}"
SERVICE="${SERVICE:-faceid}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"

gagal() { echo "GAGAL: $*" >&2; exit 1; }

HARI="$(TZ=Asia/Jakarta date +%u)"
JAM="$(TZ=Asia/Jakarta date +%H%M)"
if [ "$HARI" = "6" ] && [ "$((10#$JAM))" -ge 1500 ] && [ "$((10#$JAM))" -lt 1930 ]; then
  gagal "Sabtu 15:00–19:30 WIB adalah jendela ibadah. Jalankan di luar jam itu."
fi

cd "$APP_DIR" || gagal "folder $APP_DIR tidak ada (atur APP_DIR=...)"
[ -f .env ] || gagal ".env tidak ditemukan di $APP_DIR"
command -v openssl >/dev/null || gagal "openssl tidak terpasang"

CADANGAN=".env.bak-$(date +%Y%m%d-%H%M%S)"
cp -p .env "$CADANGAN"
chmod 600 "$CADANGAN"
SEBELUM="$(git rev-parse HEAD)"
echo "Cadangan .env : $APP_DIR/$CADANGAN"
echo "Commit lama   : $SEBELUM"

read -rsp "Tempel secret key Supabase baru (sb_secret_...), lalu Enter: " KUNCI_BARU
echo
case "$KUNCI_BARU" in
  sb_secret_*) ;;
  *) gagal "kunci harus diawali sb_secret_ (yang ditempel bukan secret key)";;
esac

# Huruf dan angka saja supaya aman di .env dan mudah diketik di HP.
PASSWORD_BARU="$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 24)"
[ "${#PASSWORD_BARU}" -eq 24 ] || gagal "pembuatan password gagal"

pulihkan() {
  echo "Mengembalikan kondisi lama..."
  cp -p "$CADANGAN" .env
  git reset --hard --quiet "$SEBELUM"
  ./venv/bin/pip install --quiet -r requirements.txt || true
  sudo systemctl restart "$SERVICE"
  echo "Sudah dikembalikan ke .env dan commit lama. Kirim keluaran di atas ke Claude."
}

echo "Mengambil kode terbaru dari main..."
git fetch --quiet origin main
git reset --hard --quiet origin/main

echo "Memasang dependensi (supabase akan naik ke >=2.28)..."
if ! ./venv/bin/pip install --quiet -r requirements.txt; then
  pulihkan; gagal "pip install gagal"
fi

# Nilai rahasia dikirim lewat variabel lingkungan, bukan argumen, supaya tidak
# terlihat di daftar proses (ps) selama skrip berjalan.
KUNCI_BARU="$KUNCI_BARU" PASSWORD_BARU="$PASSWORD_BARU" ./venv/bin/python - <<'PY'
import os, re
path = ".env"
teks = open(path).read()
for nama, env in (("SUPABASE_KEY", "KUNCI_BARU"), ("ADMIN_PASSWORD", "PASSWORD_BARU")):
    nilai = os.environ[env]
    baris = f"{nama}={nilai}"
    if re.search(rf"^(export )?{nama}\s*=", teks, flags=re.M):
        teks = re.sub(rf"^(export )?{nama}\s*=.*$", lambda m: baris, teks, flags=re.M)
    else:
        teks = teks.rstrip("\n") + "\n" + baris + "\n"
open(path, "w").write(teks)
PY
unset KUNCI_BARU
chmod 600 .env

echo "Memuat ulang layanan..."
sudo systemctl restart "$SERVICE"

echo "Menunggu aplikasi sehat (database harus terbaca dengan kunci baru)..."
for i in $(seq 1 90); do
  if curl -fsS "$HEALTH_URL" 2>/dev/null | grep -q '"status":"ok"'; then
    echo "Sehat setelah ${i} detik:"
    curl -sS "$HEALTH_URL"; echo
    echo
    echo "=================================================================="
    echo " Password admin dashboard yang BARU (hanya ditampilkan sekali):"
    echo
    echo "     $PASSWORD_BARU"
    echo
    echo " Simpan di password manager sekarang. Password lama sudah mati."
    echo "=================================================================="
    echo
    echo "Setelah disimpan, hapus cadangan yang masih berisi kredensial lama:"
    echo "  rm $APP_DIR/$CADANGAN"
    echo "Lalu kabari Claude: 'server sudah pindah kunci'."
    exit 0
  fi
  sleep 1
done

echo "Aplikasi tidak sehat dalam 90 detik. Log terakhir:"
sudo journalctl -u "$SERVICE" -n 40 --no-pager || true
pulihkan
gagal "deploy dibatalkan, kondisi lama dipulihkan"
