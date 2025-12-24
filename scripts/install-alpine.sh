#!/bin/sh
# Tunnel Server Installation Script for Alpine Linux
# Installs frp server + admin dashboard with user management

set -e

echo "Installing Tunnel Server on Alpine Linux..."

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
    curl

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

# Get configuration
printf "Enter your domain name (or leave empty to use IP): "
read DOMAIN
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

# Create frps OpenRC service
cat > /etc/init.d/frps <<'EOF'
#!/sbin/openrc-run

name="frps"
description="frp server"
command="/usr/local/bin/frps"
command_args="-c /etc/frp/frps.ini"
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

# Generate JWT secret
JWT_SECRET=$(openssl rand -hex 32)

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

# Configure firewall with UFW
echo "Configuring firewall..."

# Enable UFW if not already enabled
ufw --force enable

# Allow required ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP tunnels
ufw allow 443/tcp   # HTTPS tunnels
ufw allow 7000/tcp  # frp control
ufw allow 8000/tcp  # Admin dashboard

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

# Final status
log "Final status:"
log "  frps: $(rc-service frps status 2>&1 | head -1)"
log "  tunnel-admin: $(rc-service tunnel-admin status 2>&1 | head -1)"
log "  Port 7000: $(check_port 7000 && echo 'listening' || echo 'NOT listening')"
log "  Port 8000: $(check_port 8000 && echo 'listening' || echo 'NOT listening')"
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

# Wait for admin to start
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
echo "============================================="
echo ""
echo "Service Management Commands:"
echo "  rc-service frps status"
echo "  rc-service tunnel-admin status"
echo "  rc-service frps restart"
echo "  rc-service tunnel-admin restart"
echo ""
echo "Log Files:"
echo "  /var/log/frps.log"
echo "  /var/log/tunnel-admin.log"
echo "  /var/log/tunnel-boot.log (boot recovery)"
echo ""
echo "Admin credentials (check logs):"
cat /var/log/tunnel-admin.log 2>/dev/null | grep -A 5 "ADMIN CREDENTIALS" || echo "Check: cat /var/log/tunnel-admin.log"
echo ""
echo "Service Status:"
rc-service frps status
rc-service tunnel-admin status
echo ""
