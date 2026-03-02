#!/bin/bash
# Tunnel Server Startup Script - Ubuntu/systemd
# This is a string.Template file - use double-dollar for literal dollar signs
set -e

LOG="/var/log/tunnel-startup.log"
exec > "$$LOG" 2>&1
set -x

echo "=== Tunnel Server Startup: $$(date) ==="

# Wait for cloud-init to finish
cloud-init status --wait || true

# Update system
echo "Updating system..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

# Install dependencies
echo "Installing dependencies..."
apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    git \
    curl \
    wget \
    jq \
    sqlite3 \
    ufw \
    unzip

# Install frps
echo "Installing frp server..."
FRP_VERSION="0.52.3"
cd /tmp
wget -q "https://github.com/fatedier/frp/releases/download/v$${FRP_VERSION}/frp_$${FRP_VERSION}_linux_amd64.tar.gz"
tar -xzf "frp_$${FRP_VERSION}_linux_amd64.tar.gz"
cp "frp_$${FRP_VERSION}_linux_amd64/frps" /usr/local/bin/
chmod +x /usr/local/bin/frps
rm -rf /tmp/frp_*

# Create directories
mkdir -p /var/lib/tunnel-server
mkdir -p /etc/frp
mkdir -p /etc/tunnel-server
chmod 700 /var/lib/tunnel-server
chmod 700 /etc/tunnel-server

# Write frps config
cat > /etc/frp/frps.toml <<'FRPSEOF'
bindPort = 7000
vhostHTTPPort = 8080
vhostHTTPSPort = 8443
subDomainHost = "$tunnel_domain"

[auth]
method = "token"
token = "$frp_token"

[log]
to = "/var/log/frps.log"
level = "info"
maxDays = 7

[transport]
maxPoolCount = 10
heartbeatTimeout = 30

[webServer]
addr = "0.0.0.0"
port = 7500
user = "admin"
password = "$frps_dash_password"
FRPSEOF

# Clone repository
echo "Cloning tunnel-server from GitHub..."
REPO_URL="https://github.com/ersantana361/tunnel-server.git"
if [ -d "/opt/tunnel-server" ]; then
    cd /opt/tunnel-server
    git pull
else
    git clone "$$REPO_URL" /opt/tunnel-server
fi
cd /opt/tunnel-server
echo "Source code ready at /opt/tunnel-server"

# Python virtual environment
echo "Setting up Python environment..."
python3 -m venv /opt/tunnel-server/venv
/opt/tunnel-server/venv/bin/pip install --upgrade pip
/opt/tunnel-server/venv/bin/pip install -r requirements.txt

# Write environment file with secrets
cat > /etc/tunnel-server/env <<'ENVEOF'
JWT_SECRET=$jwt_secret
ADMIN_PASSWORD=$admin_password
ADMIN_TOKEN=$admin_token
DB_PATH=/var/lib/tunnel-server/tunnel.db
FRPS_CONFIG=/etc/frp/frps.toml
TUNNEL_DOMAIN=$tunnel_domain
NETLIFY_API_TOKEN=$netlify_api_token
NETLIFY_DNS_ZONE_ID=$netlify_dns_zone_id
FRPS_DASHBOARD_HOST=localhost
FRPS_DASHBOARD_PORT=7500
FRPS_DASHBOARD_USER=admin
FRPS_DASHBOARD_PASS=$frps_dash_password
ENVEOF
chmod 600 /etc/tunnel-server/env

# Create frps systemd service
cat > /etc/systemd/system/frps.service <<'SERVICEEOF'
[Unit]
Description=frp server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/frps -c /etc/frp/frps.toml
Restart=always
RestartSec=5
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Create tunnel-server systemd service
cat > /etc/systemd/system/tunnel-server.service <<'SERVICEEOF'
[Unit]
Description=Tunnel Server Admin Dashboard
After=network.target frps.service
Wants=frps.service

[Service]
Type=simple
WorkingDirectory=/opt/tunnel-server
EnvironmentFile=/etc/tunnel-server/env
ExecStart=/opt/tunnel-server/venv/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# SSL with Caddy (conditional on NETLIFY_API_TOKEN)
NETLIFY_TOKEN_VALUE="$netlify_api_token"
if [ -n "$$NETLIFY_TOKEN_VALUE" ]; then
    echo "Installing Caddy with Netlify DNS plugin for SSL..."

    # Install Go (need 1.22+ for xcaddy)
    GO_VERSION="1.22.5"
    wget -q "https://go.dev/dl/go$${GO_VERSION}.linux-amd64.tar.gz" -O /tmp/go.tar.gz
    rm -rf /usr/local/go
    tar -C /usr/local -xzf /tmp/go.tar.gz
    rm /tmp/go.tar.gz
    export PATH="/usr/local/go/bin:$$PATH"

    # Build Caddy with Netlify DNS plugin
    export HOME=/root
    export GOPATH=/root/go
    export GOCACHE=/root/.cache/go-build
    mkdir -p "$$GOPATH" "$$GOCACHE"

    go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
    "$$GOPATH/bin/xcaddy" build --with github.com/caddy-dns/netlify --output /usr/local/bin/caddy
    chmod +x /usr/local/bin/caddy

    mkdir -p /etc/caddy

    # Write Caddyfile - uses single quotes heredoc so shell doesn't expand
    # string.Template variables are already substituted before this script runs
    cat > /etc/caddy/Caddyfile <<'CADDYEOF'
{
    email $acme_email
}

*.$tunnel_domain {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }

    header ?Access-Control-Allow-Origin {header.Origin}
    header ?Access-Control-Allow-Methods "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    header ?Access-Control-Allow-Headers "Content-Type, Authorization, Accept, Origin, X-Requested-With"
    header ?Access-Control-Allow-Credentials "true"
    header ?Access-Control-Max-Age "86400"

    @cors_preflight method OPTIONS
    handle @cors_preflight {
        respond "" 204
    }

    handle {
        reverse_proxy localhost:8080
    }
}

$tunnel_domain {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }
    reverse_proxy localhost:8000
}

:8888 {
    respond /health "OK" 200
}
CADDYEOF

    # Create Caddy systemd service
    cat > /etc/systemd/system/caddy.service <<'SERVICEEOF'
[Unit]
Description=Caddy web server with automatic HTTPS
After=network.target frps.service
Wants=frps.service

[Service]
Type=simple
Environment=NETLIFY_TOKEN=$netlify_api_token
ExecStart=/usr/local/bin/caddy run --config /etc/caddy/Caddyfile
Restart=always
RestartSec=5
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
SERVICEEOF

    systemctl daemon-reload
    systemctl enable caddy
    echo "Caddy configured with SSL"
fi

# Configure firewall (defense in depth alongside GCP firewall)
echo "Configuring firewall..."
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 7000/tcp
ufw allow 8000/tcp
ufw allow 8888/tcp
ufw allow from 10.0.0.0/24 to any port 7500
ufw status

# Enable and start services
echo "Starting services..."
systemctl daemon-reload
systemctl enable frps
systemctl enable tunnel-server
systemctl start frps
systemctl start tunnel-server

if systemctl is-enabled caddy >/dev/null 2>&1; then
    systemctl start caddy
fi

sleep 3

# Get server IP
SERVER_IP=$$(curl -s ifconfig.me)

echo ""
echo "============================================="
echo "  INSTALLATION COMPLETE!"
echo "============================================="
echo ""
echo "Server Information:"
echo "  IP: $$SERVER_IP"
echo "  Domain: $tunnel_domain"
echo ""
echo "Admin Dashboard:"
echo "  URL: http://$$SERVER_IP:8000"
echo ""
echo "frp Dashboard (internal only):"
echo "  URL: http://$$SERVER_IP:7500"
echo "  Credentials: admin / (from Pulumi config)"
echo ""
echo "Client Connection Info:"
echo "  Server: $$SERVER_IP:7000"
echo "  Token: (from Pulumi config)"
echo ""
echo "=== Tunnel Server Startup Complete: $$(date) ==="
