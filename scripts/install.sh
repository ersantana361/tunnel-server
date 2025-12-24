#!/bin/bash
# Tunnel Server Installation Script
# Installs frp server + admin dashboard with user management

set -e

echo "🚀 Installing Tunnel Server with Admin Dashboard..."

# Check root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root: sudo ./install.sh"
    exit 1
fi

# Update system
echo "Updating system..."
apt update && apt upgrade -y

# Install dependencies
echo "Installing dependencies..."
apt install -y wget tar ufw python3 python3-pip python3-venv sqlite3

# Install frp server
echo "Installing frp server..."
FRP_VERSION="0.52.3"
cd /tmp
wget https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz
tar -xzf frp_${FRP_VERSION}_linux_amd64.tar.gz
cd frp_${FRP_VERSION}_linux_amd64
cp frps /usr/local/bin/
chmod +x /usr/local/bin/frps
cd /
rm -rf /tmp/frp_*

# Create directories
mkdir -p /opt/tunnel-server
mkdir -p /var/lib/tunnel-server
mkdir -p /etc/frp

# Get configuration
read -p "Enter your domain name (or leave empty to use IP): " DOMAIN
if [ -z "$DOMAIN" ]; then
    DOMAIN=$(curl -s ifconfig.me)
    echo "Using IP: $DOMAIN"
fi

# Generate frps config
cat > /etc/frp/frps.ini <<EOF
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = $DOMAIN

# Logging
log_file = /var/log/frps.log
log_level = info

# Connection limits
max_pool_count = 5
EOF

# Create frps systemd service
cat > /etc/systemd/system/frps.service <<EOF
[Unit]
Description=frp server
After=network.target

[Service]
Type=simple
User=root
Restart=on-failure
RestartSec=5s
ExecStart=/usr/local/bin/frps -c /etc/frp/frps.ini
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

# Install Python dependencies for admin dashboard
echo "Installing Python dependencies..."
cd /opt/tunnel-server
cat > requirements.txt <<EOF
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic[email]==2.5.3
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.1.2
python-multipart==0.0.6
PyJWT
EOF

pip3 install -r requirements.txt --break-system-packages

# Copy application files
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Create app directories
mkdir -p /opt/tunnel-server/app/models
mkdir -p /opt/tunnel-server/app/routes
mkdir -p /opt/tunnel-server/app/services
mkdir -p /opt/tunnel-server/app/templates

# Copy main entry point and app package
if [ -f "$PROJECT_DIR/main.py" ]; then
    cp "$PROJECT_DIR/main.py" /opt/tunnel-server/
    cp -r "$PROJECT_DIR/app/"* /opt/tunnel-server/app/
    echo "Application files copied"
elif [ -f "./main.py" ]; then
    cp ./main.py /opt/tunnel-server/
    cp -r ./app/* /opt/tunnel-server/app/
    echo "Application files copied"
else
    echo "Warning: main.py not found"
    echo "Please copy main.py and app/ folder to /opt/tunnel-server/"
fi

# Create admin systemd service
cat > /etc/systemd/system/tunnel-admin.service <<EOF
[Unit]
Description=Tunnel Server Admin Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tunnel-server
ExecStart=/usr/bin/python3 /opt/tunnel-server/main.py
Restart=on-failure
RestartSec=5s
Environment="JWT_SECRET=$(openssl rand -hex 32)"
Environment="DB_PATH=/var/lib/tunnel-server/tunnel.db"

[Install]
WantedBy=multi-user.target
EOF

# Configure firewall
echo "Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 7000/tcp
ufw allow 8000/tcp  # Admin dashboard
ufw --force enable

# Start services
systemctl daemon-reload
systemctl enable frps tunnel-admin
systemctl start frps
systemctl start tunnel-admin

# Wait for admin to start
sleep 3

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ INSTALLATION COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Server Information:"
echo "  IP: $SERVER_IP"
echo "  Domain: $DOMAIN"
echo ""
echo "Admin Dashboard:"
echo "  URL: http://$SERVER_IP:8000"
echo "  Check logs for admin credentials"
echo ""
echo "Client Connection Info:"
echo "  Server URL: http://$SERVER_IP:7000"
echo ""
echo "Next Steps:"
echo "1. Go to http://$SERVER_IP:8000"
echo "2. Login with admin credentials (check logs below)"
echo "3. Create users for your clients"
echo "4. Give clients their tokens"
echo ""
echo "DNS Setup (if using domain):"
echo "  Type    Name    Value"
echo "  A       @       $SERVER_IP"
echo "  A       *       $SERVER_IP"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Admin credentials (check logs):"
journalctl -u tunnel-admin -n 50 --no-pager | grep -A 5 "ADMIN CREDENTIALS"
echo ""
echo "Service Status:"
systemctl status frps --no-pager -l
systemctl status tunnel-admin --no-pager -l
echo ""
