# 🚀 Production Deployment Plan: FaceID-KP on Ubuntu 24.04 VPS

## 📋 Server Profile (Based on VPS Dashboard)
* **Provider:** Biznet Gio Cloud (Neo Virtual Compute)
* **OS:** Ubuntu 24.04 LTS (Noble Numbat)
* **Specifications:** 1 vCPU, 2 GB RAM, 60 GB Disk
* **Region:** West Java

---

## ⚠️ Critical Engineering Realities & Risk Mitigations

### 1. Memori & CPU Constraint (2 GB RAM, 1 vCPU)
* **Risiko:** Model AI (Face Detection & DeepFace Embedding) serta OpenCV memerlukan alokasi RAM yang cukup saat inisialisasi (~500MB - 1GB). Jika RAM 2 GB habis, kernel Linux akan memicu **OOM (Out-Of-Memory) Killer** dan mematikan proses FastAPI.
* **Mitigasi:**
  1. **Wajib Pasang 4 GB Swapfile**: Mengalokasikan ruang disk 60 GB sebagai virtual memory penahan beban burst.
  2. **Worker Concurrency Terukur**: Gunakan **1 atau 2 Uvicorn Workers** (`-w 1` atau `-w 2`). Jangan lebih dari 2 worker pada server 1 vCPU.

### 2. Keharusan HTTPS (SSL) untuk Kamera Web
* **Risiko:** Browser modern (Chrome, Safari iOS, Edge, Firefox) **memblokir total akses kamera (`navigator.mediaDevices.getUserMedia`)** jika aplikasi diakses melalui IP publik non-HTTPS (`http://`).
* **Mitigasi:**
  - Setup **Nginx Reverse Proxy** + **Let's Encrypt SSL (Certbot)** menggunakan domain atau subdomain (misal: `absen.gereja.org` / DuckDNS / Cloudflare).

---

## 🛠️ Step-by-Step Production Deployment Guide

### Tahap 1: Persiapan Server & Swap Memory (SSH ke Server)
```bash
# 1. Update repository & paket sistem
sudo apt update && sudo apt upgrade -y

# 2. Buat 4GB Swapfile untuk mencegah crash OOM
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 3. Install paket dependency sistem
sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx libgl1 libglib2.0-0 ufw
```

---

### Tahap 2: Konfigurasi Firewall (UFW Security)
```bash
# Buka hanya port yang diperlukan
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

---

### Tahap 3: Clone Codebase & Setup Python Virtual Environment
```bash
# 1. Clone repository ke direktori /var/www/
cd /var/www
sudo git clone https://github.com/joseperdana/faceID-KP.git
sudo chown -R $USER:$USER /var/www/faceID-KP
cd /var/www/faceID-KP

# 2. Checkout ke branch dev / staging / main
git checkout dev

# 3. Buat Virtual Environment & Install Dependencies
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn uvicorn[standard]
```

---

### Tahap 4: Konfigurasi Environment Secrets (`.env`)
Buat file `.env` di `/var/www/faceID-KP/.env`:
```ini
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key
ADMIN_PASSWORD_HASH=$2b$12$...
JWT_SECRET=your-super-secure-jwt-secret-key-32-chars-long
PHOTOBOOTH_BASE_URL=https://yourdomain.com
ENABLE_GEOFENCE=true
CHURCH_LAT=-7.9734182
CHURCH_LNG=112.6322894
GEOFENCE_RADIUS_METERS=150
SENTRY_DSN=
```

---

### Tahap 5: Setup Systemd Service Daemon (`faceid.service`)
Buat file service di `/etc/systemd/system/faceid.service`:
```ini
[Unit]
Description=FaceID KP Attendance & Photobooth Service
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/faceID-KP
Environment="PATH=/var/www/faceID-KP/venv/bin"
ExecStart=/var/www/faceID-KP/venv/bin/gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 --access-logfile - --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktifkan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable faceid
sudo systemctl start faceid
sudo systemctl status faceid
```

---

### Tahap 6: Konfigurasi Nginx Reverse Proxy & Let's Encrypt SSL
Buat file konfigurasi Nginx di `/etc/nginx/sites-available/faceid`:
```nginx
server {
    listen 80;
    server_name yourdomain.com; # Ganti dengan domain / subdomain Anda

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Aktifkan konfigurasi Nginx & Pasang SSL:
```bash
sudo ln -s /etc/nginx/sites-available/faceid /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Pasang SSL Gratis Otomatis dengan Certbot
sudo certbot --nginx -d yourdomain.com
```

---

## 🔒 Verification & Post-Deployment Checklist
- [ ] Swapfile 4 GB aktif (`free -h`).
- [ ] Service `faceid` berstatus `active (running)` (`systemctl status faceid`).
- [ ] Nginx merutekan trafik port 80/443 ke 127.0.0.1:8000.
- [ ] Akses HTTPS berjalan lancar dan browser mengizinkan kamera tanpa peringatan keamanan.
- [ ] Akses URL Kiosk (`/`), Photobooth (`/photobooth`), dan Dashboard Admin (`/dashboard`) terverifikasi.
