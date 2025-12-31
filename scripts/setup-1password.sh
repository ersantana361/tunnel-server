#!/bin/sh
# Setup 1Password secrets for tunnel-server
# Run this on your local machine BEFORE deploying to Vultr
#
# USAGE:
#   ./scripts/setup-1password.sh
#
# PREREQUISITES:
#   1. Install 1Password CLI: brew install 1password-cli (macOS) or see https://developer.1password.com/docs/cli
#   2. Sign in: op signin
#   3. Have a vault named "Tunnel" (or edit VAULT below)

set -e

# Configuration
VAULT="${VAULT:-Tunnel}"
ITEM_NAME="${ITEM_NAME:-tunnel-server}"

echo "=== Tunnel Server 1Password Setup ==="
echo ""

# Check if op is installed
if ! command -v op >/dev/null 2>&1; then
    echo "ERROR: 1Password CLI (op) not found"
    echo ""
    echo "Install it:"
    echo "  macOS:  brew install 1password-cli"
    echo "  Linux:  https://developer.1password.com/docs/cli/get-started"
    exit 1
fi

# Check if signed in by actually trying to list vaults
echo "Checking 1Password connection..."
if ! op vault list >/dev/null 2>&1; then
    echo ""
    echo "ERROR: Cannot connect to 1Password"
    echo ""
    echo "Options:"
    echo "  1. Enable desktop app integration (recommended):"
    echo "     https://developer.1password.com/docs/cli/app-integration/"
    echo ""
    echo "  2. Sign in manually:"
    echo "     op account add"
    echo "     op signin"
    echo ""
    echo "  3. Use service account token:"
    echo "     export OP_SERVICE_ACCOUNT_TOKEN='ops_...'"
    echo ""
    exit 1
fi

echo "Connected to 1Password"

# Check if vault exists
if ! op vault get "$VAULT" >/dev/null 2>&1; then
    echo "Creating vault: $VAULT"
    op vault create "$VAULT"
else
    echo "Using existing vault: $VAULT"
fi

# Generate secrets
echo ""
echo "Generating secrets..."
JWT_SECRET=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d '=')
ADMIN_TOKEN=$(openssl rand -hex 32)
FRP_TOKEN=$(openssl rand -hex 32)
DASH_PASSWORD=$(openssl rand -hex 16)

# Prompt for optional values
echo ""
read -p "Enter domain (e.g., tunnel.example.com) [leave empty to use IP]: " DOMAIN
read -p "Enter Netlify API token [leave empty to skip]: " NETLIFY_TOKEN
read -p "Enter ACME email for SSL certs [admin@localhost]: " ACME_EMAIL
ACME_EMAIL="${ACME_EMAIL:-admin@localhost}"

# Check if item already exists
if op item get "$ITEM_NAME" --vault "$VAULT" >/dev/null 2>&1; then
    echo ""
    echo "Item '$ITEM_NAME' already exists in vault '$VAULT'"
    read -p "Overwrite? (y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
    echo "Deleting existing item..."
    op item delete "$ITEM_NAME" --vault "$VAULT"
fi

# Build the item creation command
echo ""
echo "Creating 1Password item..."

# Create the item with all fields
TEMPLATE=$(cat <<EOF
{
  "title": "$ITEM_NAME",
  "category": "SERVER",
  "fields": [
    {"id": "jwt-secret", "type": "CONCEALED", "label": "jwt-secret", "value": "$JWT_SECRET"},
    {"id": "admin-password", "type": "CONCEALED", "label": "admin-password", "value": "$ADMIN_PASSWORD"},
    {"id": "admin-token", "type": "CONCEALED", "label": "admin-token", "value": "$ADMIN_TOKEN"},
    {"id": "frp-token", "type": "CONCEALED", "label": "frp-token", "value": "$FRP_TOKEN"},
    {"id": "dash-password", "type": "CONCEALED", "label": "dash-password", "value": "$DASH_PASSWORD"},
    {"id": "domain", "type": "STRING", "label": "domain", "value": "$DOMAIN"},
    {"id": "netlify-token", "type": "CONCEALED", "label": "netlify-token", "value": "$NETLIFY_TOKEN"},
    {"id": "acme-email", "type": "STRING", "label": "acme-email", "value": "$ACME_EMAIL"}
  ]
}
EOF
)

echo "$TEMPLATE" | op item create --vault "$VAULT"

echo ""
echo "============================================="
echo "  1Password Setup Complete!"
echo "============================================="
echo ""
echo "Vault: $VAULT"
echo "Item:  $ITEM_NAME"
echo ""
echo "Generated secrets:"
echo "  jwt-secret:         ****${JWT_SECRET: -8}"
echo "  admin-password:     $ADMIN_PASSWORD"
echo "  admin-token:        ****${ADMIN_TOKEN: -8}"
echo "  frp-token:          ****${FRP_TOKEN: -8}"
echo "  dash-password:      $DASH_PASSWORD"
if [ -n "$DOMAIN" ]; then
echo "  domain:             $DOMAIN"
fi
if [ -n "$NETLIFY_TOKEN" ]; then
echo "  netlify-token:      ****${NETLIFY_TOKEN: -8}"
fi
echo "  acme-email:         $ACME_EMAIL"
echo ""
echo "Next steps:"
echo ""
echo "  1. Create a service account for server access:"
echo "     https://my.1password.com → Settings → Service Accounts"
echo "     Grant it access to the '$VAULT' vault"
echo ""
echo "  2. Copy the service account token and paste it in:"
echo "     scripts/vultr-startup.sh → OP_SERVICE_ACCOUNT_TOKEN"
echo ""
echo "  3. Deploy to Vultr with the startup script"
echo ""
echo "To view secrets later:"
echo "  op item get $ITEM_NAME --vault $VAULT"
echo ""
echo "To read a specific field:"
echo "  op read 'op://$VAULT/$ITEM_NAME/admin-password'"
echo ""
