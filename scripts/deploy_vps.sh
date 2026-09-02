#!/usr/bin/env bash
set -e

echo "🚀 Starting Production Deployment for FaceID-KP..."

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
PROJECT_DIR="/var/www/faceID-KP"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "📂 Cloning repository to $PROJECT_DIR..."
    sudo mkdir -p /var/www
    sudo chown -R $USER:$USER /var/www
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
pip install gunicorn uvicorn[standard]

# 5. Setup Systemd Service
echo "⚙️ Configuring systemd service (faceid.service)..."
sudo bash -c "cat << 'EOF' > /etc/systemd/system/faceid.service
[Unit]
Description=FaceID KP Attendance & Photobooth Service
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/faceID-KP
Environment=\"PATH=/var/www/faceID-KP/venv/bin\"
ExecStart=/var/www/faceID-KP/venv/bin/gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 --access-logfile - --error-logfile -
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
