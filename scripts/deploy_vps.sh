#!/usr/bin/env bash
# PEMASANGAN AWAL di VPS Ubuntu yang MASIH KOSONG. Bukan untuk memperbarui.
#
# Skrip ini menulis ulang unit systemd dan konfigurasi Nginx dengan versi HTTP
# polos. Di server yang sudah berjalan, itu mematikan HTTPS — dan tanpa HTTPS
# peramban menolak akses kamera, jadi semua kiosk mati. Untuk memperbarui kode
# di server yang sudah hidup, pakai scripts/remote_update.sh.
#
# Isinya disamakan dengan produksi per September 2026: SATU proses uvicorn di
# $HOME/faceID-KP. Bukan gunicorn dengan 2 worker: server KP hanya 1 vCPU, dan
# worker kedua berarti salinan model wajah kedua (~1 GB RAM) tanpa tambahan
# prosesor. Penyebab macet saat Gibbor bukan kurang worker, melainkan event
# loop yang terblokir (lihat docs/v3/postmortem-gibbor-2026.md).
set -euo pipefail

if [ -f /etc/systemd/system/faceid.service ] || [ -f /etc/nginx/sites-available/faceid ]; then
    echo "Server ini sudah terpasang (unit faceid atau site Nginx faceid sudah ada)."
    echo "Skrip ini hanya untuk server kosong dan akan menimpa konfigurasi HTTPS."
    echo "Untuk memperbarui kode: scripts/remote_update.sh"
    exit 1
fi

PROJECT_DIR="${PROJECT_DIR:-$HOME/faceID-KP}"
RUN_USER="$(id -un)"

echo "Memasang FaceID-KP di $PROJECT_DIR sebagai pengguna $RUN_USER..."

# 1. Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt install -y python3-pip python3-venv git nginx libgl1 libglib2.0-0 ufw

# 2. Setup 4GB Swap Memory (Vital for 2GB RAM VPS to prevent OOM crash)
if [ ! -f /swapfile ]; then
    echo "🧠 Creating 4GB Swapfile..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✅ 4GB Swapfile activated!"
else
    echo "✅ Swapfile already exists."
fi

# 3. Setup Project Directory
if [ ! -d "$PROJECT_DIR" ]; then
    echo "📂 Cloning repository to $PROJECT_DIR..."
    git clone https://github.com/joseperdana/faceID-KP.git "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"
echo "🔄 Pulling latest main branch..."
git fetch origin
git checkout main
git pull origin main

# 4. Virtual Environment & Dependencies
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Setup Systemd Service
echo "⚙️ Configuring systemd service (faceid.service)..."
sudo bash -c "cat << 'EOF' > /etc/systemd/system/faceid.service
[Unit]
Description=FaceID KP Attendance & Photobooth Service
After=network.target

[Service]
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR
Environment=\"PATH=$PROJECT_DIR/venv/bin\"
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable faceid
sudo systemctl restart faceid
echo "✅ faceid.service started!"

# 6. Configure Nginx Reverse Proxy
echo "🌐 Configuring Nginx reverse proxy..."
sudo bash -c "cat << 'EOF' > /etc/nginx/sites-available/faceid
server {
    listen 80;
    server_name _;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF"

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/faceid /etc/nginx/sites-enabled/faceid
sudo nginx -t
sudo systemctl restart nginx
echo "✅ Nginx reverse proxy reloaded!"

echo ""
echo "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "📍 App is live at: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip')"
echo ""
echo "Langkah wajib berikutnya: pasang HTTPS. Tanpa HTTPS peramban menolak kamera."
echo "  sudo apt install -y certbot python3-certbot-nginx"
echo "  sudo certbot --nginx -d <domain-anda>"
echo "Lalu: journald (scripts/ops/journald-retention.conf) dan pemantau uptime"
echo "(docs/v3/runbooks/uptime-monitoring.md)."
