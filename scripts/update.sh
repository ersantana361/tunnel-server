#!/bin/sh
# Update tunnel-server from GitHub and restart
# Run this script ON the server as root

set -e

REMOTE_DIR="/opt/tunnel-server"
REPO_URL="https://github.com/ersantana361/tunnel-server.git"

echo "=== Tunnel Server Update ==="
echo ""

# Check if running as root
if [ "$(id -u)" != "0" ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

cd "$REMOTE_DIR"

# Check if it's a git repo, if not clone it
if [ ! -d ".git" ]; then
    echo "Git repo not found. Cloning from GitHub..."
    cd /opt
    rm -rf tunnel-server
    git clone "$REPO_URL" tunnel-server
    cd tunnel-server

    # Create virtual environment
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Pulling latest changes from GitHub..."
    git fetch origin
    git reset --hard origin/main
fi

# Activate virtual environment and install dependencies
echo ""
echo "Installing dependencies..."
. venv/bin/activate
pip install -q -r requirements.txt

# Restart the service
echo ""
echo "Restarting tunnel-server service..."
rc-service tunnel-server restart

# Show status
echo ""
echo "=== Update Complete ==="
rc-service tunnel-server status

echo ""
echo "Logs: tail -f /var/log/tunnel-server.log"
