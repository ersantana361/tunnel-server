#!/bin/sh
# Deploy tunnel-server to Alpine Linux server
# Usage: TUNNEL_SERVER_IP=your-ip ./deploy.sh

set -e

# Check for IP
if [ -z "$TUNNEL_SERVER_IP" ]; then
    echo "Error: TUNNEL_SERVER_IP environment variable not set"
    echo ""
    echo "Usage:"
    echo "  TUNNEL_SERVER_IP=123.45.67.89 ./deploy.sh"
    echo ""
    echo "Or export it:"
    echo "  export TUNNEL_SERVER_IP=123.45.67.89"
    echo "  ./deploy.sh"
    exit 1
fi

SERVER="root@$TUNNEL_SERVER_IP"
REMOTE_DIR="/opt/tunnel-server"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# SSH control socket for connection reuse (one password prompt)
SOCKET="/tmp/ssh-deploy-$$"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=$SOCKET -o ControlPersist=60"

cleanup() {
    ssh -O exit -o ControlPath=$SOCKET "$SERVER" 2>/dev/null || true
}
trap cleanup EXIT

echo "Deploying to $TUNNEL_SERVER_IP..."

# Start master connection (one password prompt)
echo "Connecting..."
ssh $SSH_OPTS -o ControlMaster=yes -N -f "$SERVER"

# Create remote directories
echo "Creating remote directories..."
ssh $SSH_OPTS "$SERVER" "mkdir -p $REMOTE_DIR/app/models $REMOTE_DIR/app/routes $REMOTE_DIR/app/services $REMOTE_DIR/app/templates"

# Upload files using the shared connection
echo "Uploading files..."
scp $SSH_OPTS "$PROJECT_DIR/main.py" "$SERVER:$REMOTE_DIR/"
scp $SSH_OPTS "$PROJECT_DIR/requirements.txt" "$SERVER:$REMOTE_DIR/"

scp $SSH_OPTS "$PROJECT_DIR/app/__init__.py" "$SERVER:$REMOTE_DIR/app/"
scp $SSH_OPTS "$PROJECT_DIR/app/config.py" "$SERVER:$REMOTE_DIR/app/"
scp $SSH_OPTS "$PROJECT_DIR/app/database.py" "$SERVER:$REMOTE_DIR/app/"
scp $SSH_OPTS "$PROJECT_DIR/app/dependencies.py" "$SERVER:$REMOTE_DIR/app/"

scp $SSH_OPTS "$PROJECT_DIR/app/models/__init__.py" "$SERVER:$REMOTE_DIR/app/models/"
scp $SSH_OPTS "$PROJECT_DIR/app/models/schemas.py" "$SERVER:$REMOTE_DIR/app/models/"

scp $SSH_OPTS "$PROJECT_DIR/app/routes/__init__.py" "$SERVER:$REMOTE_DIR/app/routes/"
scp $SSH_OPTS "$PROJECT_DIR/app/routes/auth.py" "$SERVER:$REMOTE_DIR/app/routes/"
scp $SSH_OPTS "$PROJECT_DIR/app/routes/users.py" "$SERVER:$REMOTE_DIR/app/routes/"
scp $SSH_OPTS "$PROJECT_DIR/app/routes/tunnels.py" "$SERVER:$REMOTE_DIR/app/routes/"
scp $SSH_OPTS "$PROJECT_DIR/app/routes/ssh_keys.py" "$SERVER:$REMOTE_DIR/app/routes/"
scp $SSH_OPTS "$PROJECT_DIR/app/routes/stats.py" "$SERVER:$REMOTE_DIR/app/routes/"

scp $SSH_OPTS "$PROJECT_DIR/app/services/__init__.py" "$SERVER:$REMOTE_DIR/app/services/"
scp $SSH_OPTS "$PROJECT_DIR/app/services/auth.py" "$SERVER:$REMOTE_DIR/app/services/"
scp $SSH_OPTS "$PROJECT_DIR/app/services/tunnel.py" "$SERVER:$REMOTE_DIR/app/services/"
scp $SSH_OPTS "$PROJECT_DIR/app/services/activity.py" "$SERVER:$REMOTE_DIR/app/services/"

scp $SSH_OPTS "$PROJECT_DIR/app/templates/dashboard.html" "$SERVER:$REMOTE_DIR/app/templates/"

echo ""
echo "Files uploaded to $TUNNEL_SERVER_IP:$REMOTE_DIR"
echo ""
echo "Restarting service..."
ssh $SSH_OPTS "$SERVER" "rc-service tunnel-admin restart"

echo ""
echo "Done! Check status:"
echo "  ssh $SERVER rc-service tunnel-admin status"
