#!/bin/sh
# Phase 2: Start tunnel-server with 1Password secrets
# This script is called by the OpenRC service or can be run manually

set -e

# Change to project directory
cd "$(dirname "$0")/.."

# Source 1Password token if running interactively
if [ -f /etc/profile.d/1password.sh ]; then
    . /etc/profile.d/1password.sh
fi

# Check for 1Password token
if [ -z "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
    echo "Warning: OP_SERVICE_ACCOUNT_TOKEN not set"
    echo "Secrets will not be injected from 1Password"
    echo ""
    echo "For production, set the token:"
    echo "  export OP_SERVICE_ACCOUNT_TOKEN=\"ops_...\""
    echo ""
    echo "Starting without 1Password (using env vars or defaults)..."
    . venv/bin/activate
    exec python3 main.py
fi

# Activate virtual environment
. venv/bin/activate

# Run with 1Password secret injection
exec op run --env-file=.env.1password -- python3 main.py
