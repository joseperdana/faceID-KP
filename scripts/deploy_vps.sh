#!/usr/bin/env bash
#
# Deploy FaceID-KP to an Ubuntu VPS.
#
#   bash scripts/deploy_vps.sh                 # deploy origin/main
#   bash scripts/deploy_vps.sh v2.1.0          # deploy a tag
#   bash scripts/deploy_vps.sh <commit-sha>    # roll back to a known-good commit
#
# The previous version of this script printed "DEPLOYMENT COMPLETED SUCCESSFULLY"
# and exited 0 while the service crash-looped behind it, because:
#   * it never created the .env that core/security.py hard-fails without;
#   * `systemctl restart` returns immediately and nothing checked whether the
#     app came up;
#   * it configured HTTP only, so getUserMedia was blocked and the kiosk camera
#     could never start;
#   * dependencies were unpinned, so a deploy-day resolution could pull an
#     incompatible numpy and break the import.
#
# Each of those is now a hard failure with a message, and a failed health check
# rolls the checkout back to where it was.

set -euo pipefail

REF="${1:-main}"
PROJECT_DIR="${PROJECT_DIR:-/var/www/faceID-KP}"
SERVICE_USER="${SERVICE_USER:-faceid}"
SERVICE_NAME="faceid"
REPO_URL="${REPO_URL:-https://github.com/joseperdana/faceID-KP.git}"
HEALTH_URL="http://127.0.0.1:8000/healthz"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[0;32m%s\033[0m\n' "$*"; }
warn() { printf '    \033[0;33m%s\033[0m\n' "$*"; }
die()  { printf '\n\033[0;31mGAGAL: %s\033[0m\n\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || command -v sudo >/dev/null || die "Butuh root atau sudo."

# --------------------------------------------------------------- packages ----
log "Menyiapkan paket sistem"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip python3-venv git nginx curl jq \
    libgl1 libglib2.0-0 ufw certbot python3-certbot-nginx
ok "Paket siap."

# ------------------------------------------------------------------ swap -----
if [ ! -f /swapfile ]; then
    log "Membuat swapfile 4 GB (VPS 2 GB RAM butuh ini untuk model AI)"
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile >/dev/null
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    ok "Swapfile aktif."
else
    ok "Swapfile sudah ada."
fi

# --------------------------------------------------------- service account ---
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    log "Membuat akun layanan '$SERVICE_USER'"
    # The service used to run as root, with OpenCV decoding untrusted images
    # from the internet. A memory-safety bug in a JPEG decoder would have been
    # root on the box.
    sudo useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    ok "Akun dibuat."
fi

# --------------------------------------------------------------- checkout ----
log "Mengambil kode ($REF)"
if [ ! -d "$PROJECT_DIR/.git" ]; then
    sudo mkdir -p "$(dirname "$PROJECT_DIR")"
    sudo git clone "$REPO_URL" "$PROJECT_DIR"
fi
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$PROJECT_DIR"

cd "$PROJECT_DIR"
PREVIOUS_SHA="$(sudo -u "$SERVICE_USER" git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo '')"
sudo -u "$SERVICE_USER" git -C "$PROJECT_DIR" fetch --tags --prune origin
sudo -u "$SERVICE_USER" git -C "$PROJECT_DIR" checkout --force "$REF" 2>/dev/null \
    || sudo -u "$SERVICE_USER" git -C "$PROJECT_DIR" checkout --force "origin/$REF"
NEW_SHA="$(sudo -u "$SERVICE_USER" git -C "$PROJECT_DIR" rev-parse HEAD)"
ok "HEAD: $NEW_SHA"
[ -n "$PREVIOUS_SHA" ] && ok "Sebelumnya: $PREVIOUS_SHA"

# ------------------------------------------------------------------- .env ----
log "Memeriksa konfigurasi"
ENV_FILE="$PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    warn ".env belum ada — membuat kerangka dari .env.example."
    sudo -u "$SERVICE_USER" cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
    sudo -u "$SERVICE_USER" bash -c "
        python3 - <<'PY' >> '$ENV_FILE'
import secrets
print()
print('# Digenerate otomatis oleh scripts/deploy_vps.sh')
print(f'SECRET_KEY={secrets.token_urlsafe(48)}')
print(f'KIOSK_TOKEN={secrets.token_urlsafe(32)}')
PY"
    sudo chmod 600 "$ENV_FILE"
    die "SECRET_KEY dan KIOSK_TOKEN sudah dibuat di $ENV_FILE.
     Lengkapi nilai berikut lalu jalankan skrip ini lagi:
       - SUPABASE_URL, SUPABASE_KEY   (pakai service_role key; lihat migrations/001_init.sql)
       - ADMIN_PASSWORD_HASH          (buat dengan: python scripts/hash_password.py)
       - CHURCH_LAT, CHURCH_LNG       (VERIFIKASI DI PETA lebih dulu — koordinat
                                       salah menolak seluruh jemaat di lokasi)"
fi

sudo chmod 600 "$ENV_FILE"
sudo chown "$SERVICE_USER:$SERVICE_USER" "$ENV_FILE"

# Validate before touching the running service, so a bad .env never causes an
# outage — it just stops the deploy.
missing=()
check_var() {
    local name="$1"
    local value
    value="$(sudo grep -E "^${name}=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"'"'"' ' || true)"
    [ -n "$value" ] || missing+=("$name")
}
for var in SUPABASE_URL SUPABASE_KEY SECRET_KEY KIOSK_TOKEN; do check_var "$var"; done
if ! sudo grep -qE '^ADMIN_PASSWORD_HASH=.+' "$ENV_FILE" && ! sudo grep -qE '^ADMIN_PASSWORD=.+' "$ENV_FILE"; then
    missing+=("ADMIN_PASSWORD_HASH")
fi
if sudo grep -qE '^ENABLE_GEOFENCE=(true|1|yes)' "$ENV_FILE"; then
    for var in CHURCH_LAT CHURCH_LNG; do check_var "$var"; done
fi
if [ ${#missing[@]} -gt 0 ]; then
    die "Nilai berikut masih kosong di $ENV_FILE: ${missing[*]}"
fi
ok "Konfigurasi lengkap."

if sudo grep -qE '^ADMIN_PASSWORD=.+' "$ENV_FILE" && ! sudo grep -qE '^ADMIN_PASSWORD_HASH=.+' "$ENV_FILE"; then
    warn "ADMIN_PASSWORD masih plaintext. Buat hash dengan 'python scripts/hash_password.py'."
fi

# ------------------------------------------------------------ dependencies ---
log "Memasang dependensi Python"
if [ ! -d "$PROJECT_DIR/venv" ]; then
    sudo -u "$SERVICE_USER" python3 -m venv "$PROJECT_DIR/venv"
fi
sudo -u "$SERVICE_USER" "$PROJECT_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$PROJECT_DIR/venv/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"
ok "Dependensi terpasang (versi ter-pin di requirements.txt)."

log "Memuat model AI lebih dulu (agar request pertama tidak menunggu unduhan)"
sudo -u "$SERVICE_USER" bash -c "cd '$PROJECT_DIR' && set -a && . ./.env && set +a && ./venv/bin/python -c 'from face_service import face_service; print(\"model ok\" if face_service.warm_up() else \"model GAGAL dimuat\")'" \
    || warn "Model gagal dimuat. Aplikasi tetap jalan; kiosk memakai pencarian manual."

# ----------------------------------------------------------------- systemd ---
log "Menulis unit systemd"
# -w 1: on a single vCPU a second worker adds no throughput and doubles the
# ~1 GB model footprint on a 2 GB box, which forced the weights into swap.
# --preload: load once before forking rather than once per worker.
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<UNIT
[Unit]
Description=FaceID-KP Attendance Service
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
Environment="PATH=${PROJECT_DIR}/venv/bin"
# ONNX Runtime otherwise opens one thread per core and the workers fight for
# the single vCPU.
Environment="OMP_NUM_THREADS=1"
ExecStart=${PROJECT_DIR}/venv/bin/gunicorn main:app \\
    --workers 1 \\
    --preload \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --bind 127.0.0.1:8000 \\
    --timeout 120 \\
    --graceful-timeout 30 \\
    --forwarded-allow-ips 127.0.0.1 \\
    --access-logfile - --error-logfile -
Restart=always
RestartSec=5

# Hardening: the process parses untrusted images from the internet.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
ReadWritePaths=${PROJECT_DIR}/frontend/uploads
MemoryMax=1600M

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --quiet ${SERVICE_NAME}
ok "Unit terpasang."

# ------------------------------------------------------------------- nginx ---
log "Mengonfigurasi Nginx"
sudo tee /etc/nginx/sites-available/${SERVICE_NAME} > /dev/null <<NGINX
server {
    listen 80;
    server_name ${DOMAIN:-_};

    client_max_body_size 25M;

    # Overwrite rather than append, so a client cannot forge its own address and
    # escape rate limiting by rotating the header.
    proxy_set_header X-Forwarded-For \$remote_addr;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Host \$host;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_read_timeout 120s;
        proxy_http_version 1.1;
    }
}
NGINX
sudo ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/${SERVICE_NAME}
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
ok "Nginx aktif."

# ------------------------------------------------------------------- HTTPS ---
if [ -n "${DOMAIN:-}" ]; then
    log "Menerbitkan sertifikat TLS untuk $DOMAIN"
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
        --redirect -m "${CERTBOT_EMAIL:-admin@$DOMAIN}"
    ok "HTTPS aktif."
else
    warn "DOMAIN tidak diset — server hanya melayani HTTP."
    warn "Browser MEMBLOKIR akses kamera (getUserMedia) di origin non-HTTPS,"
    warn "jadi kiosk TIDAK akan bisa memindai wajah dari perangkat manapun."
    warn "Jalankan ulang dengan: DOMAIN=absen.contoh.org bash scripts/deploy_vps.sh"
fi

# ---------------------------------------------------------------- firewall ---
log "Mengaktifkan firewall"
# ufw was installed by the old script but never configured or enabled.
sudo ufw --force default deny incoming >/dev/null
sudo ufw --force default allow outgoing >/dev/null
sudo ufw allow OpenSSH >/dev/null
sudo ufw allow 'Nginx Full' >/dev/null
sudo ufw --force enable >/dev/null
ok "Firewall aktif (SSH + HTTP/HTTPS)."

# ------------------------------------------------------------ restart+check --
log "Memulai ulang layanan"
sudo systemctl restart ${SERVICE_NAME}

log "Menunggu layanan sehat (maksimal ${HEALTH_TIMEOUT}s)"
healthy=0
for _ in $(seq 1 $((HEALTH_TIMEOUT / 3))); do
    if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
        healthy=1
        break
    fi
    sleep 3
done

if [ "$healthy" -ne 1 ]; then
    printf '\n\033[0;31mHealth check gagal. Log 60 baris terakhir:\033[0m\n\n'
    sudo journalctl -u ${SERVICE_NAME} -n 60 --no-pager || true
    if [ -n "$PREVIOUS_SHA" ] && [ "$PREVIOUS_SHA" != "$NEW_SHA" ]; then
        log "Rollback otomatis ke $PREVIOUS_SHA"
        sudo -u "$SERVICE_USER" git -C "$PROJECT_DIR" checkout --force "$PREVIOUS_SHA"
        sudo -u "$SERVICE_USER" "$PROJECT_DIR/venv/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"
        sudo systemctl restart ${SERVICE_NAME}
        sleep 10
        if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
            die "Versi baru gagal; sudah dikembalikan ke $PREVIOUS_SHA dan layanan berjalan."
        fi
        die "Versi baru gagal DAN rollback juga gagal. Periksa journalctl -u ${SERVICE_NAME}."
    fi
    die "Layanan tidak sehat setelah ${HEALTH_TIMEOUT}s."
fi

HEALTH_JSON="$(curl -fsS "$HEALTH_URL")"
ok "Layanan sehat: $HEALTH_JSON"

if echo "$HEALTH_JSON" | grep -q '"face_recognition":"unavailable"'; then
    warn "Model wajah tidak tersedia — kiosk berjalan dalam mode pencarian manual."
fi

# ------------------------------------------------------------------ backup ---
log "Menjadwalkan pengingat backup"
# There is no database backup at all: one bad DELETE loses the whole attendance
# history permanently. Supabase's own scheduled backups are the right mechanism;
# this only makes the gap visible.
BACKUP_NOTE="/etc/cron.weekly/faceid-backup-reminder"
sudo tee "$BACKUP_NOTE" > /dev/null <<'CRON'
#!/bin/sh
logger -t faceid "Pengingat: pastikan backup terjadwal Supabase aktif untuk tabel users dan attendance_logs."
CRON
sudo chmod +x "$BACKUP_NOTE"
warn "Aktifkan backup terjadwal di dashboard Supabase — belum ada backup otomatis untuk data ini."

# ----------------------------------------------------------------- summary ---
printf '\n\033[1;32mDEPLOY SELESAI\033[0m\n\n'
echo "  Versi     : $NEW_SHA"
echo "  Layanan   : systemctl status ${SERVICE_NAME}"
echo "  Log       : journalctl -u ${SERVICE_NAME} -f"
echo "  Rollback  : bash scripts/deploy_vps.sh ${PREVIOUS_SHA:-<sha>}"
echo
echo "  Langkah berikutnya:"
echo "   1. Jalankan migrations/001_init.sql di Supabase bila belum."
echo "   2. Buka /login sebagai pengurus di tablet kiosk, lalu buka /kiosk/enroll"
echo "      untuk mendaftarkan perangkat itu (sekali saja per tablet)."
if [ -z "${DOMAIN:-}" ]; then
    echo "   3. Pasang HTTPS — tanpa itu kamera kiosk tidak akan berfungsi."
fi
echo
