#!/bin/sh
# Phase 1: Install tunnel-server with 1Password integration (Alpine Linux)
# Usage: wget -qO- https://raw.githubusercontent.com/ersantana361/tunnel-server/main/scripts/install.sh | sh

set -e

INSTALL_DIR="${INSTALL_DIR:-/opt/tunnel-server}"
REPO_URL="https://github.com/ersantana361/tunnel-server.git"
OP_VERSION="${OP_VERSION:-2.30.0}"

echo "==> Installing tunnel-server to ${INSTALL_DIR}"

# 1. Install system dependencies
echo "==> Installing system dependencies..."
apk update
apk add python3 py3-pip py3-virtualenv git curl unzip

# 2. Install 1Password CLI (Alpine uses static binary)
echo "==> Installing 1Password CLI v${OP_VERSION}..."
if ! command -v op >/dev/null 2>&1; then
    curl -sSfLo /tmp/op.zip "https://cache.agilebits.com/dist/1P/op2/pkg/v${OP_VERSION}/op_linux_amd64_v${OP_VERSION}.zip"
    unzip -o /tmp/op.zip -d /usr/local/bin
    rm /tmp/op.zip
    chmod +x /usr/local/bin/op
    echo "    1Password CLI installed: $(op --version)"
else
    echo "    1Password CLI already installed: $(op --version)"
fi

# 3. Clone repository
echo "==> Cloning repository..."
if [ -d "$INSTALL_DIR" ]; then
    echo "    Directory exists, pulling latest..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 4. Create virtual environment and install Python deps
echo "==> Setting up Python virtual environment..."
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create .env.1password template
echo "==> Creating .env.1password template..."
cat > .env.1password << 'EOF'
JWT_SECRET=op://Tunnel/tunnel-server/jwt-secret
ADMIN_PASSWORD=op://Tunnel/tunnel-server/admin-password
ADMIN_TOKEN=op://Tunnel/tunnel-server/admin-token
DB_PATH=/var/lib/tunnel-server/tunnel.db
EOF

# 6. Create data directory
echo "==> Creating data directory..."
mkdir -p /var/lib/tunnel-server
chmod 700 /var/lib/tunnel-server

# 7. Create OpenRC service
echo "==> Creating OpenRC service..."
cat > /etc/init.d/tunnel-server << 'EOF'
#!/sbin/openrc-run

name="tunnel-server"
description="Tunnel Server with 1Password secrets"

command="/opt/tunnel-server/scripts/start.sh"
command_background="yes"
pidfile="/run/${RC_SVCNAME}.pid"
output_log="/var/log/tunnel-server.log"
error_log="/var/log/tunnel-server.log"

# Retry stopping: SIGTERM, wait 5s, SIGTERM, wait 5s, SIGKILL
retry="TERM/5/TERM/5/KILL/5"

depend() {
    need net
    after firewall
}

start_pre() {
    # Source 1Password token if available
    if [ -f /etc/profile.d/1password.sh ]; then
        . /etc/profile.d/1password.sh
    fi

    # Verify 1Password token is set
    if [ -z "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
        eerror "OP_SERVICE_ACCOUNT_TOKEN not set!"
        eerror "Create /etc/profile.d/1password.sh with:"
        eerror "  export OP_SERVICE_ACCOUNT_TOKEN=\"ops_...\""
        return 1
    fi
}

stop() {
    ebegin "Stopping ${name}"
    # Kill the main process from pidfile
    if [ -f "$pidfile" ]; then
        start-stop-daemon --stop --pidfile "$pidfile" --retry "$retry"
    fi
    # Also kill any remaining Python processes for this app
    pkill -f "python.*main.py.*tunnel-server" 2>/dev/null || true
    pkill -f "/opt/tunnel-server/venv/bin/python" 2>/dev/null || true
    rm -f "$pidfile"
    eend 0
}
EOF

chmod +x /etc/init.d/tunnel-server

# 8. Make start script executable
chmod +x "$INSTALL_DIR/scripts/start.sh"

echo ""
echo "=============================================="
echo "  Installation complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Create 1Password service account:"
echo "     https://my.1password.com → Settings → Service Accounts"
echo ""
echo "  2. Create 'Tunnel' vault with 'tunnel-server' item containing:"
echo "     - jwt-secret     (generate: openssl rand -hex 32)"
echo "     - admin-password (your chosen password)"
echo "     - admin-token    (generate: openssl rand -hex 32)"
echo ""
echo "  3. Set service account token:"
echo "     cat > /etc/profile.d/1password.sh << 'EOF'"
echo "     export OP_SERVICE_ACCOUNT_TOKEN=\"ops_your_token_here\""
echo "     EOF"
echo "     source /etc/profile.d/1password.sh"
echo ""
echo "  4. Start the service:"
echo "     rc-service tunnel-server start"
echo "     rc-update add tunnel-server default"
echo ""
echo "  5. Access dashboard at http://your-server:8000"
echo ""
