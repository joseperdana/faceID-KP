#!/usr/bin/env bash
# Pembaruan aplikasi di VPS. Dipasang di server sebagai /usr/local/bin/deploy-faceid.sh
# dan dikunci sebagai satu-satunya perintah yang boleh dijalankan kunci deploy
# (lihat command="..." di authorized_keys). Kunci itu karena itu tidak bisa
# membuka shell, membaca .env, atau menyentuh database — kalau bocor, kerugian
# terburuknya adalah seseorang memicu deploy ulang.
#
# SENGAJA TIDAK menyentuh Nginx maupun systemd unit. scripts/deploy_vps.sh
# menulis ulang konfigurasi Nginx dengan versi HTTP polos; menjalankannya di
# server yang sudah ber-HTTPS akan mematikan kamera di semua kiosk, karena
# peramban hanya mengizinkan akses kamera di konteks aman.

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/var/www/faceID-KP}"
SERVICE="${SERVICE:-faceid}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"

cd "$PROJECT_DIR"

SEBELUM="$(git rev-parse HEAD)"
echo "▶ Versi sekarang: $SEBELUM"

git fetch --quiet origin main
SESUDAH="$(git rev-parse origin/main)"

if [ "$SEBELUM" = "$SESUDAH" ]; then
  echo "✓ Sudah versi terbaru, tidak ada yang perlu dilakukan."
  exit 0
fi

echo "▶ Memperbarui ke: $SESUDAH"
# reset --hard, bukan pull: server adalah tujuan deploy, bukan tempat menyunting.
# Kalau ada yang pernah mengedit langsung di server, perubahan itu memang harus
# hilang — diam-diam menyimpannya justru membuat server berbeda dari repo.
git reset --hard --quiet "$SESUDAH"

echo "▶ Menyamakan dependensi..."
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt

echo "▶ Memuat ulang layanan..."
sudo systemctl restart "$SERVICE"

echo "▶ Menunggu aplikasi sehat..."
for i in $(seq 1 90); do
  if curl -fsS "$HEALTH_URL" > /dev/null 2>&1; then
    echo "✓ Sehat setelah ${i} detik."
    curl -sS "$HEALTH_URL" || true
    echo
    echo "✅ Deploy selesai: $SEBELUM → $SESUDAH"
    exit 0
  fi
  sleep 1
done

# Gagal sehat: kembalikan ke versi sebelumnya. Kiosk yang jalan dengan versi lama
# jauh lebih baik daripada kiosk yang mati dengan versi baru — apalagi kalau ini
# terjadi saat ibadah sedang berlangsung.
echo "::error::Aplikasi tidak sehat dalam 90 detik. Mengembalikan ke $SEBELUM"
git reset --hard --quiet "$SEBELUM"
./venv/bin/pip install --quiet -r requirements.txt || true
sudo systemctl restart "$SERVICE"
sleep 10
if curl -fsS "$HEALTH_URL" > /dev/null 2>&1; then
  echo "✓ Berhasil kembali ke versi sebelumnya. Aplikasi hidup lagi."
else
  echo "::error::Pengembalian juga gagal. Butuh penanganan manual di server."
fi
exit 1
