#!/bin/sh
# Tunnel Server Installation Script for Alpine Linux
# Installs frp server + admin dashboard with user management

set -e

echo "Installing Tunnel Server on Alpine Linux..."

# Fetch secrets from management server Vault (VPC-only)
# VAULT_TOKEN: Vault deploy token for secrets access
# VAULT_ADDR: Vault server address (defaults to 10.0.0.10:8200)
CODE_FROM_MGMT=false
if [ -n "$VAULT_TOKEN" ]; then
    VAULT_ADDR="${VAULT_ADDR:-http://10.0.0.10:8200}"
    FILE_SERVER="${FILE_SERVER:-http://10.0.0.10:8080}"
    echo "Fetching secrets from Vault at $VAULT_ADDR..."

    # Test Vault connectivity
    vault_health=$(curl -sf "${VAULT_ADDR}/v1/sys/health" 2>/dev/null || echo "")
    if [ -z "$vault_health" ]; then
        echo "ERROR: Cannot connect to Vault at $VAULT_ADDR"
        exit 1
    fi
    if echo "$vault_health" | grep -q '"sealed":true'; then
        echo "ERROR: Vault is sealed"
        exit 1
    fi

    # Fetch all secrets from Vault in single API call
    echo "Fetching secrets from Vault..."
    SECRETS=$(curl -sf -H "X-Vault-Token: ${VAULT_TOKEN}" \
        "${VAULT_ADDR}/v1/secret/data/projects/tunnel-server/env")

    if [ -z "$SECRETS" ]; then
        echo "ERROR: Failed to fetch secrets from Vault"
        echo "Path: secret/data/projects/tunnel-server/env"
        exit 1
    fi

    # Extract individual values
    NETLIFY_TOKEN=$(echo "$SECRETS" | jq -r '.data.data.NETLIFY_TOKEN // empty')
    FRP_TOKEN=$(echo "$SECRETS" | jq -r '.data.data.FRP_TOKEN // empty')
    DOMAIN=$(echo "$SECRETS" | jq -r '.data.data.DOMAIN // empty')
    DASH_PASS=$(echo "$SECRETS" | jq -r '.data.data.DASH_PASS // empty')
    JWT_SECRET=$(echo "$SECRETS" | jq -r '.data.data.JWT_SECRET // empty')

    # Validate required secrets
    if [ -z "$FRP_TOKEN" ]; then
        echo "ERROR: FRP_TOKEN not found in Vault"
        exit 1
    fi

    if [ -z "$NETLIFY_TOKEN" ]; then
        echo "Warning: NETLIFY_TOKEN not found, SSL will be disabled"
    fi

    if [ -z "$DASH_PASS" ]; then
        DASH_PASS=$(openssl rand -hex 16)
        echo "Warning: DASH_PASS not in Vault, generated: $DASH_PASS"
    fi

    echo "Secrets loaded from Vault"

    # Download code from HTTP file server (NO PASSWORD - VPC-only access)
    echo "Downloading code from HTTP server (VPC-only, no auth)..."
    mkdir -p /opt/tunnel-server/app

    cd /opt/tunnel-server
    if wget -q $FILE_SERVER/tunnel-server/main.py -O main.py 2>/dev/null; then
        # Download app directory as tarball
        wget -q $FILE_SERVER/tunnel-server/app.tar.gz -O /tmp/app.tar.gz
        tar -xzf /tmp/app.tar.gz -C /opt/tunnel-server/
        rm -f /tmp/app.tar.gz
        echo "Code downloaded from HTTP server"
        CODE_FROM_MGMT=true
    else
        echo "Note: Code not available from HTTP server, will use local files"
    fi
fi

# Defaults
ACME_EMAIL="${ACME_EMAIL:-admin@localhost}"

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root: sudo ./install-alpine.sh"
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
    jq

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
mkdir -p /var/log

# Get configuration - use vault-provided domain or fall back to IP
if [ -z "$DOMAIN" ]; then
    DOMAIN=$(curl -s ifconfig.me)
    echo "Using IP: $DOMAIN"
else
    echo "Using domain: $DOMAIN"
fi

# Generate frps config (TOML format)
# FRP_TOKEN must be set (from Vault or generate one)
FRP_TOKEN="${FRP_TOKEN:-$(openssl rand -hex 32)}"
DASH_PASS="${DASH_PASS:-$(openssl rand -hex 16)}"

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
cat > /etc/init.d/frps <<'EOF'
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
EOF
chmod +x /etc/init.d/frps

# Install Python dependencies for admin dashboard
echo "Installing Python dependencies..."
cd /opt/tunnel-server

# Create virtual environment to avoid system package conflicts
python3 -m venv /opt/tunnel-server/venv

# Install dependencies in virtual environment
/opt/tunnel-server/venv/bin/pip install --upgrade pip
/opt/tunnel-server/venv/bin/pip install \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.5.3 \
    'pydantic[email]==2.5.3' \
    'python-jose[cryptography]==3.3.0' \
    'passlib[bcrypt]==1.7.4' \
    bcrypt==4.1.2 \
    python-multipart==0.0.6 \
    PyJWT

# Copy application files (skip if downloaded from management server)
if [ "$CODE_FROM_MGMT" = "false" ]; then
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
    elif [ -f "$SCRIPT_DIR/main.py" ]; then
        cp "$SCRIPT_DIR/main.py" /opt/tunnel-server/
        cp -r "$SCRIPT_DIR/app/"* /opt/tunnel-server/app/
        echo "Application files copied"
    elif [ -f "./main.py" ]; then
        cp ./main.py /opt/tunnel-server/
        cp -r ./app/* /opt/tunnel-server/app/
        echo "Application files copied"
    else
        echo "Warning: main.py not found"
        echo "Please copy main.py and app/ folder to /opt/tunnel-server/"
    fi
fi

# Generate JWT secret (use Vault value if available, otherwise generate new)
JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"

# Create tunnel-admin OpenRC service
cat > /etc/init.d/tunnel-admin <<EOF
#!/sbin/openrc-run

name="tunnel-admin"
description="Tunnel Server Admin Dashboard"
command="/opt/tunnel-server/venv/bin/python3"
command_args="/opt/tunnel-server/main.py"
command_background=true
pidfile="/run/\${RC_SVCNAME}.pid"
directory="/opt/tunnel-server"
output_log="/var/log/tunnel-admin.log"
error_log="/var/log/tunnel-admin.log"

export JWT_SECRET="$JWT_SECRET"
export DB_PATH="/var/lib/tunnel-server/tunnel.db"

depend() {
    need net
    after frps
}

start_pre() {
    checkpath --directory --owner root:root --mode 0755 /var/lib/tunnel-server
}
EOF
chmod +x /etc/init.d/tunnel-admin

# SSL Configuration with Caddy (automatic if NETLIFY_TOKEN is available)
SSL_ENABLED=false
if [ -n "$NETLIFY_TOKEN" ]; then
    echo "Installing Caddy with Netlify DNS plugin for SSL..."

    # Install Go for building Caddy
    apk add --no-cache go

    # Build Caddy with Netlify DNS plugin
    export GOPATH=/root/go
    export PATH=$PATH:$GOPATH/bin
    go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
    $GOPATH/bin/xcaddy build --with github.com/caddy-dns/netlify --output /usr/local/bin/caddy
    chmod +x /usr/local/bin/caddy

    # Create Caddy config directory
    mkdir -p /etc/caddy

    # Create Caddyfile
    cat > /etc/caddy/Caddyfile <<EOF
{
    email $ACME_EMAIL
}

# Wildcard cert for all tunnel subdomains
*.${DOMAIN} {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }
    reverse_proxy localhost:8080
}

# Admin dashboard with SSL
${DOMAIN} {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }
    reverse_proxy localhost:8000
}

# Health check endpoint (no TLS)
:8888 {
    respond /health "OK" 200
}
EOF

    # Create Caddy OpenRC service
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

export NETLIFY_TOKEN="$NETLIFY_TOKEN"

depend() {
    need net
    after frps
}
EOF
    chmod +x /etc/init.d/caddy

    # Update frps to use internal port (Caddy handles 80/443)
    sed -i 's/vhost_http_port = 80/vhost_http_port = 8080/' /etc/frp/frps.ini
    sed -i 's/vhost_https_port = 443/vhost_https_port = 8443/' /etc/frp/frps.ini

    # Enable Caddy
    rc-update add caddy default

    SSL_ENABLED=true
    echo "SSL configured with Caddy"
fi

# Configure firewall with UFW
echo "Configuring firewall..."

# Enable UFW if not already enabled
ufw --force enable

# Allow required ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Caddy)
ufw allow 443/tcp   # HTTPS (Caddy)
ufw allow 7000/tcp  # frp bind port
ufw allow 8000/tcp  # Python admin dashboard
ufw allow 8888/tcp  # Health check endpoint
ufw allow from 10.0.0.0/24 to any port 7500  # frp dashboard (VPC only)

# Show status
ufw status

# Create tunnel server boot script (health check & recovery)
echo "Creating boot recovery script..."
cat > /etc/local.d/tunnel-server.start <<'EOF'
#!/bin/sh
# Tunnel Server Boot Script - Full Recovery

LOG="/var/log/tunnel-boot.log"
MAX_RETRIES=3
RETRY_DELAY=5

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

check_port() {
    netstat -tuln 2>/dev/null | grep -q ":$1 " || \
    ss -tuln 2>/dev/null | grep -q ":$1 "
}

cleanup_pid() {
    local pidfile="/run/$1.pid"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$pidfile"
            log "Cleaned stale PID file: $pidfile"
        fi
    fi
}

start_service() {
    local service=$1
    local port=$2
    local attempt=1

    while [ $attempt -le $MAX_RETRIES ]; do
        log "Starting $service (attempt $attempt/$MAX_RETRIES)"
        rc-service "$service" start >/dev/null 2>&1
        sleep 3

        if rc-service "$service" status >/dev/null 2>&1; then
            if [ -n "$port" ]; then
                sleep 2
                if check_port "$port"; then
                    log "$service started OK (port $port listening)"
                    return 0
                fi
            else
                log "$service started OK"
                return 0
            fi
        fi

        log "$service failed to start, retrying..."
        rc-service "$service" stop >/dev/null 2>&1
        sleep $RETRY_DELAY
        attempt=$((attempt + 1))
    done

    log "ERROR: $service failed after $MAX_RETRIES attempts"
    return 1
}

# Main
log "=== Tunnel Server Boot Check ==="

# Cleanup stale PIDs
cleanup_pid frps
cleanup_pid tunnel-admin
cleanup_pid caddy

# Check/start frps
if ! rc-service frps status >/dev/null 2>&1; then
    start_service frps 7000
elif ! check_port 7000; then
    log "frps running but port 7000 not listening, restarting..."
    rc-service frps restart >/dev/null 2>&1
    sleep 3
fi

# Check/start tunnel-admin
if ! rc-service tunnel-admin status >/dev/null 2>&1; then
    start_service tunnel-admin 8000
elif ! check_port 8000; then
    log "tunnel-admin running but port 8000 not listening, restarting..."
    rc-service tunnel-admin restart >/dev/null 2>&1
    sleep 3
fi

# Check/start caddy (if installed)
if [ -f /etc/init.d/caddy ]; then
    if ! rc-service caddy status >/dev/null 2>&1; then
        start_service caddy 443
    elif ! check_port 443; then
        log "caddy running but port 443 not listening, restarting..."
        rc-service caddy restart >/dev/null 2>&1
        sleep 3
    fi
fi

# Final status
log "Final status:"
log "  frps: $(rc-service frps status 2>&1 | head -1)"
log "  tunnel-admin: $(rc-service tunnel-admin status 2>&1 | head -1)"
if [ -f /etc/init.d/caddy ]; then
log "  caddy: $(rc-service caddy status 2>&1 | head -1)"
fi
log "  Port 7000: $(check_port 7000 && echo 'listening' || echo 'NOT listening')"
log "  Port 7500: $(check_port 7500 && echo 'listening' || echo 'NOT listening')"
log "  Port 8000: $(check_port 8000 && echo 'listening' || echo 'NOT listening')"
if [ -f /etc/init.d/caddy ]; then
log "  Port 443: $(check_port 443 && echo 'listening' || echo 'NOT listening')"
log "  Port 8888: $(check_port 8888 && echo 'listening' || echo 'NOT listening')"
fi
log "=== Boot check complete ==="
EOF
chmod +x /etc/local.d/tunnel-server.start

# Enable local service for iptables restore and boot script
rc-update add local default 2>/dev/null || true

# Enable and start services
echo "Starting services..."
rc-update add frps default
rc-update add tunnel-admin default
rc-service frps start
rc-service tunnel-admin start

# Start Caddy if SSL enabled
if [ "$SSL_ENABLED" = "true" ]; then
    rc-service caddy start
fi

# Wait for services to start
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
echo "  Check logs for admin credentials"
echo ""
echo "frp Dashboard (VPC only):"
echo "  URL: http://$SERVER_IP:7500"
echo "  Credentials: admin / ${DASH_PASS}"
echo ""
echo "Health Check:"
echo "  URL: http://$SERVER_IP:8888/health"
echo ""
echo "Client Connection Info:"
echo "  Server: $SERVER_IP:7000"
echo "  Token: ${FRP_TOKEN}"
echo ""
if [ "$SSL_ENABLED" = "true" ]; then
echo "SSL Configuration:"
echo "  Tunnels: https://*.${DOMAIN}"
echo "  Admin: https://${DOMAIN}"
echo "  Certificates auto-renew via Let's Encrypt"
echo ""
fi
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
echo "============================================="
echo ""
echo "Service Management Commands:"
echo "  rc-service frps status"
echo "  rc-service tunnel-admin status"
if [ "$SSL_ENABLED" = "true" ]; then
echo "  rc-service caddy status"
fi
echo "  rc-service frps restart"
echo "  rc-service tunnel-admin restart"
if [ "$SSL_ENABLED" = "true" ]; then
echo "  rc-service caddy restart"
fi
echo ""
echo "Log Files:"
echo "  /var/log/frps.log"
echo "  /var/log/tunnel-admin.log"
if [ "$SSL_ENABLED" = "true" ]; then
echo "  /var/log/caddy.log"
fi
echo "  /var/log/tunnel-boot.log (boot recovery)"
echo ""
echo "Admin credentials (check logs):"
cat /var/log/tunnel-admin.log 2>/dev/null | grep -A 5 "ADMIN CREDENTIALS" || echo "Check: cat /var/log/tunnel-admin.log"
echo ""
echo "Service Status:"
rc-service frps status
rc-service tunnel-admin status
if [ "$SSL_ENABLED" = "true" ]; then
rc-service caddy status
fi
echo ""
