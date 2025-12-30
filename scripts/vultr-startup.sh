#!/bin/sh
# Vultr Startup Script - Tunnel Server with 1Password
# Single file that does everything - paste into Vultr Console
#
# USAGE:
# 1. Fill in OP_SERVICE_ACCOUNT_TOKEN below
# 2. Copy this entire script into Vultr Console:
#    Products -> Startup Scripts -> Add Startup Script
# 3. When deploying a new Alpine VM, select this startup script
#
# PREREQUISITES:
# 1. Create 1Password service account at https://my.1password.com
# 2. Create "Tunnel" vault with "tunnel-server" item containing:
#    - jwt-secret (openssl rand -hex 32)
#    - admin-password (your chosen password)
#    - admin-token (openssl rand -hex 32)
#    - frp-token (openssl rand -hex 32)
#    - domain (your domain, e.g., tunnel.example.com)
#    - netlify-token (optional, for SSL via Caddy)
#    - dash-password (optional, frp dashboard password)

set -e

LOG="/var/log/tunnel-bootstrap.log"
exec > "$LOG" 2>&1
set -x

echo "=== Tunnel Server Bootstrap Started: $(date) ==="

# ============================================================
# CONFIGURATION - Fill in this value before deploying
# ============================================================

# 1Password Service Account Token
OP_SERVICE_ACCOUNT_TOKEN='ops_'
export OP_SERVICE_ACCOUNT_TOKEN

# Optional settings
ACME_EMAIL="admin@localhost"

# ============================================================
# DO NOT EDIT BELOW THIS LINE
# ============================================================

# Validate token is set
if [ "$OP_SERVICE_ACCOUNT_TOKEN" = "ops_PASTE_YOUR_TOKEN_HERE" ] || [ -z "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
    echo "ERROR: OP_SERVICE_ACCOUNT_TOKEN not configured!"
    echo "Edit this script and paste your 1Password service account token"
    exit 1
fi

# Wait for network
echo "Waiting for network..."
sleep 10

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Must run as root"
    exit 1
fi

# Update system
echo "Updating system..."
apk update && apk upgrade

# Install dependencies
echo "Installing dependencies..."
apk add --no-cache \
    wget \
    tar \
    python3 \
    py3-pip \
    sqlite \
    openssl \
    ufw \
    curl \
    jq \
    unzip \
    git

# Install 1Password CLI
echo "Installing 1Password CLI..."
OP_VERSION="2.30.0"
if ! command -v op >/dev/null 2>&1; then
    curl -sSfLo /tmp/op.zip "https://cache.agilebits.com/dist/1P/op2/pkg/v${OP_VERSION}/op_linux_amd64_v${OP_VERSION}.zip"
    unzip -o /tmp/op.zip -d /usr/local/bin
    rm /tmp/op.zip
    chmod +x /usr/local/bin/op
fi
echo "1Password CLI version: $(op --version)"

# Test 1Password connection
echo "Testing 1Password connection..."
if ! op vault list >/dev/null 2>&1; then
    echo "ERROR: Cannot connect to 1Password. Check your service account token."
    exit 1
fi
echo "1Password connection successful"

# Fetch secrets from 1Password
echo "Fetching secrets from 1Password..."
JWT_SECRET=$(op read "op://Tunnel/tunnel-server/jwt-secret" 2>/dev/null || echo "")
ADMIN_PASSWORD=$(op read "op://Tunnel/tunnel-server/admin-password" 2>/dev/null || echo "")
ADMIN_TOKEN=$(op read "op://Tunnel/tunnel-server/admin-token" 2>/dev/null || echo "")
FRP_TOKEN=$(op read "op://Tunnel/tunnel-server/frp-token" 2>/dev/null || echo "")
DOMAIN=$(op read "op://Tunnel/tunnel-server/domain" 2>/dev/null || echo "")
NETLIFY_TOKEN=$(op read "op://Tunnel/tunnel-server/netlify-token" 2>/dev/null || echo "")
DASH_PASS=$(op read "op://Tunnel/tunnel-server/dash-password" 2>/dev/null || echo "")

# Validate required secrets
if [ -z "$FRP_TOKEN" ]; then
    echo "ERROR: frp-token not found in 1Password (op://Tunnel/tunnel-server/frp-token)"
    exit 1
fi

if [ -z "$JWT_SECRET" ]; then
    JWT_SECRET=$(openssl rand -hex 32)
    echo "Warning: jwt-secret not in 1Password, generated temporary one"
fi

if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD=$(openssl rand -base64 16)
    echo "Warning: admin-password not in 1Password, generated: $ADMIN_PASSWORD"
fi

if [ -z "$ADMIN_TOKEN" ]; then
    ADMIN_TOKEN=$(openssl rand -hex 32)
    echo "Warning: admin-token not in 1Password, generated temporary one"
fi

if [ -z "$DASH_PASS" ]; then
    DASH_PASS=$(openssl rand -hex 16)
    echo "Warning: dash-password not in 1Password, generated: $DASH_PASS"
fi

if [ -z "$NETLIFY_TOKEN" ]; then
    echo "Warning: netlify-token not found, SSL will be disabled"
fi

echo "Secrets loaded successfully"

# Save 1Password token for future use
echo "Saving 1Password token..."
cat > /etc/profile.d/1password.sh << EOF
export OP_SERVICE_ACCOUNT_TOKEN="${OP_SERVICE_ACCOUNT_TOKEN}"
EOF
chmod 600 /etc/profile.d/1password.sh

# Clone repository from GitHub
echo "Cloning tunnel-server from GitHub..."
REPO_URL="https://github.com/ersantana361/tunnel-server.git"
if [ -d "/opt/tunnel-server" ]; then
    cd /opt/tunnel-server
    git pull
else
    git clone "$REPO_URL" /opt/tunnel-server
fi
cd /opt/tunnel-server
echo "Source code ready at /opt/tunnel-server"

# Install frp server
echo "Installing frp server..."
FRP_VERSION="0.52.3"
cd /tmp
wget -q https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz
tar -xzf frp_${FRP_VERSION}_linux_amd64.tar.gz
cp frp_${FRP_VERSION}_linux_amd64/frps /usr/local/bin/
chmod +x /usr/local/bin/frps
rm -rf /tmp/frp_*

# Create directories
mkdir -p /var/lib/tunnel-server
mkdir -p /etc/frp
mkdir -p /var/log
chmod 700 /var/lib/tunnel-server

# Get domain or fall back to IP
if [ -z "$DOMAIN" ]; then
    DOMAIN=$(curl -s ifconfig.me)
    echo "Using IP: $DOMAIN"
else
    echo "Using domain: $DOMAIN"
fi

# Generate frps config
cat > /etc/frp/frps.toml <<EOF
bindPort = 7000
vhostHTTPPort = 8080
vhostHTTPSPort = 8443
subDomainHost = "${DOMAIN}"

[auth]
method = "token"
token = "${FRP_TOKEN}"

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
password = "${DASH_PASS}"
EOF

echo "frp dashboard credentials: admin / ${DASH_PASS}"

# Create frps OpenRC service
cat > /etc/init.d/frps <<'FRPS_SERVICE'
#!/sbin/openrc-run

name="frps"
description="frp server"
command="/usr/local/bin/frps"
command_args="-c /etc/frp/frps.toml"
command_background=true
pidfile="/run/${RC_SVCNAME}.pid"
output_log="/var/log/frps.log"
error_log="/var/log/frps.log"

depend() {
    need net
    after firewall
}
FRPS_SERVICE
chmod +x /etc/init.d/frps

# Install Python dependencies
echo "Installing Python dependencies..."
cd /opt/tunnel-server

python3 -m venv /opt/tunnel-server/venv

/opt/tunnel-server/venv/bin/pip install --upgrade pip
/opt/tunnel-server/venv/bin/pip install -r requirements.txt

# Create .env.1password for the app
cat > /opt/tunnel-server/.env.1password <<EOF
JWT_SECRET=op://Tunnel/tunnel-server/jwt-secret
ADMIN_PASSWORD=op://Tunnel/tunnel-server/admin-password
ADMIN_TOKEN=op://Tunnel/tunnel-server/admin-token
DB_PATH=/var/lib/tunnel-server/tunnel.db
EOF

# Create tunnel-server OpenRC service (with 1Password)
cat > /etc/init.d/tunnel-server <<'EOF'
#!/sbin/openrc-run

name="tunnel-server"
description="Tunnel Server Admin Dashboard"
command="/opt/tunnel-server/scripts/start.sh"
command_background=true
pidfile="/run/${RC_SVCNAME}.pid"
directory="/opt/tunnel-server"
output_log="/var/log/tunnel-server.log"
error_log="/var/log/tunnel-server.log"

depend() {
    need net
    after frps
}

start_pre() {
    # Source 1Password token
    if [ -f /etc/profile.d/1password.sh ]; then
        . /etc/profile.d/1password.sh
    fi

    if [ -z "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
        eerror "OP_SERVICE_ACCOUNT_TOKEN not set!"
        return 1
    fi

    checkpath --directory --owner root:root --mode 0700 /var/lib/tunnel-server
}
EOF
chmod +x /etc/init.d/tunnel-server

# Make start script executable
chmod +x /opt/tunnel-server/scripts/start.sh

# SSL Configuration with Caddy (if NETLIFY_TOKEN is available)
SSL_ENABLED=false
if [ -n "$NETLIFY_TOKEN" ]; then
    echo "Installing Caddy with Netlify DNS plugin for SSL..."

    apk add --no-cache go

    # Set Go environment (required for startup script context)
    export HOME=/root
    export GOPATH=/root/go
    export GOCACHE=/root/.cache/go-build
    export TMPDIR=/root/tmp
    export PATH=$PATH:$GOPATH/bin
    mkdir -p "$GOCACHE" "$TMPDIR"

    go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
    $GOPATH/bin/xcaddy build --with github.com/caddy-dns/netlify --output /usr/local/bin/caddy
    chmod +x /usr/local/bin/caddy

    mkdir -p /etc/caddy

    cat > /etc/caddy/Caddyfile <<EOF
{
    email ${ACME_EMAIL}
}

*.${DOMAIN} {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }
    reverse_proxy localhost:8080
}

${DOMAIN} {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }
    reverse_proxy localhost:8000
}

:8888 {
    respond /health "OK" 200
}
EOF

    cat > /etc/init.d/caddy <<EOF
#!/sbin/openrc-run

name="caddy"
description="Caddy web server with automatic HTTPS"
command="/usr/local/bin/caddy"
command_args="run --config /etc/caddy/Caddyfile"
command_background=true
pidfile="/run/\${RC_SVCNAME}.pid"
output_log="/var/log/caddy.log"
error_log="/var/log/caddy.log"

export NETLIFY_TOKEN="${NETLIFY_TOKEN}"

depend() {
    need net
    after frps
}
EOF
    chmod +x /etc/init.d/caddy

    rc-update add caddy default
    SSL_ENABLED=true
    echo "SSL configured with Caddy"
fi

# Configure firewall
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

# Create boot recovery script
cat > /etc/local.d/tunnel-server.start <<'BOOT_SCRIPT'
#!/bin/sh
LOG="/var/log/tunnel-boot.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

check_port() {
    netstat -tuln 2>/dev/null | grep -q ":$1 " || ss -tuln 2>/dev/null | grep -q ":$1 "
}

log "=== Tunnel Server Boot Check ==="

# Source 1Password token
if [ -f /etc/profile.d/1password.sh ]; then
    . /etc/profile.d/1password.sh
fi

for svc in frps tunnel-server caddy; do
    if [ -f /etc/init.d/$svc ]; then
        if ! rc-service $svc status >/dev/null 2>&1; then
            log "Starting $svc..."
            rc-service $svc start
        fi
    fi
done

log "=== Boot check complete ==="
BOOT_SCRIPT
chmod +x /etc/local.d/tunnel-server.start

rc-update add local default 2>/dev/null || true

# Enable and start services
echo "Starting services..."
rc-update add frps default
rc-update add tunnel-server default
rc-service frps start

# Source 1Password token before starting tunnel-server
. /etc/profile.d/1password.sh
rc-service tunnel-server start

if [ "$SSL_ENABLED" = "true" ]; then
    rc-service caddy start
fi

sleep 3

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

echo ""
echo "============================================="
echo "  INSTALLATION COMPLETE!"
echo "============================================="
echo ""
echo "Server Information:"
echo "  IP: $SERVER_IP"
echo "  Domain: $DOMAIN"
echo ""
echo "Python Admin Dashboard:"
echo "  URL: http://$SERVER_IP:8000"
echo "  Credentials: admin@localhost / (from 1Password)"
echo ""
echo "frp Dashboard (VPC only):"
echo "  URL: http://$SERVER_IP:7500"
echo "  Credentials: admin / ${DASH_PASS}"
echo ""
echo "Client Connection Info:"
echo "  Server: $SERVER_IP:7000"
echo "  Token: (from 1Password: op://Tunnel/tunnel-server/frp-token)"
echo ""
if [ "$SSL_ENABLED" = "true" ]; then
echo "SSL Configuration:"
echo "  Tunnels: https://*.${DOMAIN}"
echo "  Admin: https://${DOMAIN}"
echo ""
fi
echo "Secrets managed by 1Password:"
echo "  Vault: Tunnel"
echo "  Item: tunnel-server"
echo ""
echo "============================================="
echo ""
echo "=== Tunnel Server Bootstrap Complete: $(date) ==="
