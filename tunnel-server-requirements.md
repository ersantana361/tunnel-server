# Tunnel Server Requirements

This document specifies what a tunnel server must implement to bootstrap itself using 1Password for secrets management.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    BOOTSTRAP FLOW                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Tunnel Server starts with OP_SERVICE_ACCOUNT_TOKEN     │
│                          │                                  │
│                          ▼                                  │
│  2. Install 1Password CLI (op)                             │
│                          │                                  │
│                          ▼                                  │
│  3. Fetch secrets from 1Password:                          │
│     • JWT secret                                           │
│     • Admin password                                       │
│     • Admin tunnel token                                   │
│     • frp authentication token                             │
│     • Netlify API token (for DNS)                          │
│                          │                                  │
│                          ▼                                  │
│  4. Clone project from GitHub                              │
│                          │                                  │
│                          ▼                                  │
│  5. Configure and start services:                          │
│     • tunnel-admin (FastAPI app)                           │
│     • frps (tunnel server)                                 │
│     • Caddy (TLS termination with Netlify DNS)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

Before bootstrap, the tunnel server needs:

| Requirement | Value | How to Get |
|-------------|-------|------------|
| Public IP | Vultr/cloud instance | Deploy new instance |
| 1Password service account | `ops_xxxxx` token | Create at my.1password.com |
| 1Password vault | "Tunnel" | Create vault and item |
| Internet access | Public IP | Vultr public network |

---

## Step 1: Set Up 1Password Secrets

### Create Service Account

1. Go to https://my.1password.com
2. Developer Tools → Service Accounts → Create Service Account
3. Name it (e.g., "tunnel-server-prod")
4. Grant access to "Tunnel" vault (read-only)
5. Copy the token (`ops_xxxxx...`)

### Generate and Store Secrets

Run locally with 1Password CLI:

```bash
# Install 1Password CLI
brew install 1password-cli  # macOS

# Sign in
op signin

# Generate secrets and save to vault
./scripts/setup-1password.sh
```

This creates item `tunnel-server` in vault `Tunnel` with:

| Field | Description |
|-------|-------------|
| `jwt-secret` | JWT signing key (64 hex chars) |
| `admin-password` | Admin dashboard password (22 chars) |
| `admin-token` | Admin tunnel token (64 hex chars) |
| `frp-token` | frp authentication token (64 hex chars) |
| `netlify-token` | Netlify API token (for DNS challenges) |
| `domain` | Server domain (e.g., tunnel.example.com) |

---

## Step 2: Environment Variables

The bootstrap script requires this environment variable:

```bash
# Required - 1Password service account token
export OP_SERVICE_ACCOUNT_TOKEN="ops_xxxxx..."
```

---

## Step 3: Fetch Secrets from 1Password

### Using 1Password CLI

```bash
# Read individual secrets
op read "op://Tunnel/tunnel-server/jwt-secret"
op read "op://Tunnel/tunnel-server/admin-password"
op read "op://Tunnel/tunnel-server/frp-token"

# Or use op run with env file
op run --env-file=.env.1password -- python3 main.py
```

### Required Secrets

#### 3.1 JWT Secret

```bash
JWT_SECRET=$(op read "op://Tunnel/tunnel-server/jwt-secret")
```

**Used for:** Signing JWT tokens for dashboard authentication

---

#### 3.2 Admin Credentials

```bash
ADMIN_PASSWORD=$(op read "op://Tunnel/tunnel-server/admin-password")
ADMIN_TOKEN=$(op read "op://Tunnel/tunnel-server/admin-token")
```

**Used for:** Admin dashboard login and tunnel authentication

---

#### 3.3 frp Authentication Token

```bash
FRP_TOKEN=$(op read "op://Tunnel/tunnel-server/frp-token")
```

**Used for:** frp client authentication (clients must use same token)

---

#### 3.4 Netlify API Token

```bash
NETLIFY_TOKEN=$(op read "op://Tunnel/tunnel-server/netlify-token")
```

**Used for:** Caddy DNS challenge (wildcard TLS certificates via Netlify DNS)

---

## Step 4: Clone Project from GitHub

```bash
git clone https://github.com/ersantana361/tunnel-server.git /opt/tunnel-server
cd /opt/tunnel-server
```

---

## Step 5: Configuration Files to Generate

### 5.1 frp Server Config (`/etc/frp/frps.ini`)

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = tunnel.ersantana.com
authentication_method = token
token = ${FRP_TOKEN}        # From 1Password

log_file = /var/log/frps.log
log_level = info
log_max_days = 7
```

---

### 5.2 Caddy Config (`/etc/caddy/Caddyfile`)

```caddyfile
{
    email admin@yourdomain.com
    acme_dns netlify {env.NETLIFY_TOKEN}
}

*.tunnel.ersantana.com {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }
    reverse_proxy localhost:80
}

tunnel.ersantana.com {
    tls {
        dns netlify {env.NETLIFY_TOKEN}
    }
    reverse_proxy localhost:8000
}

:8888 {
    respond /health "OK" 200
}
```

---

### 5.3 Environment File (`.env.1password`)

```bash
JWT_SECRET=op://Tunnel/tunnel-server/jwt-secret
ADMIN_PASSWORD=op://Tunnel/tunnel-server/admin-password
ADMIN_TOKEN=op://Tunnel/tunnel-server/admin-token
DB_PATH=/var/lib/tunnel-server/tunnel.db
```

---

## Step 6: Services to Start

| Service | Binary | Config | Ports |
|---------|--------|--------|-------|
| tunnel-admin | Python/uvicorn | `.env.1password` | 8000 |
| frps | `/usr/local/bin/frps` | `/etc/frp/frps.ini` | 7000, 80, 443 |
| caddy | `/usr/local/bin/caddy` | `/etc/caddy/Caddyfile` | 443 (TLS) |

### Alpine Linux (OpenRC) Commands

```bash
rc-update add tunnel-admin default
rc-update add frps default
rc-update add caddy default
rc-service tunnel-admin start
rc-service frps start
rc-service caddy start
```

---

## Step 7: Firewall Rules

```bash
# Allow public
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (frp tunnels)
ufw allow 443/tcp   # HTTPS (Caddy TLS)
ufw allow 7000/tcp  # frp bind port
ufw allow 8000/tcp  # Admin dashboard (or restrict)

ufw enable
```

---

## Complete Bootstrap Script

The `scripts/vultr-startup.sh` script implements this flow. Key steps:

```bash
#!/bin/sh
set -e

# 1. Validate environment
if [ -z "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
    echo "Error: OP_SERVICE_ACCOUNT_TOKEN required"
    exit 1
fi

# 2. Install 1Password CLI
apk add --no-cache curl jq
curl -sS https://downloads.1password.com/linux/op2/pkg/v2.32.0/op_linux_amd64_v2.32.0.zip -o op.zip
unzip op.zip && mv op /usr/local/bin/ && chmod +x /usr/local/bin/op

# 3. Test 1Password connectivity
op vault list >/dev/null || { echo "1Password auth failed"; exit 1; }

# 4. Fetch secrets from 1Password
JWT_SECRET=$(op read "op://Tunnel/tunnel-server/jwt-secret")
ADMIN_PASSWORD=$(op read "op://Tunnel/tunnel-server/admin-password")
ADMIN_TOKEN=$(op read "op://Tunnel/tunnel-server/admin-token")
FRP_TOKEN=$(op read "op://Tunnel/tunnel-server/frp-token")
NETLIFY_TOKEN=$(op read "op://Tunnel/tunnel-server/netlify-token")
DOMAIN=$(op read "op://Tunnel/tunnel-server/domain")

# 5. Clone project
git clone https://github.com/ersantana361/tunnel-server.git /opt/tunnel-server
cd /opt/tunnel-server

# 6. Install Python dependencies
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt

# 7. Install frp
FRP_VERSION="0.52.3"
wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz"
tar -xzf frp_*.tar.gz && mv frp_*/frps /usr/local/bin/

# 8. Generate frps.ini
cat > /etc/frp/frps.ini << EOF
[common]
bind_port = 7000
vhost_http_port = 80
subdomain_host = ${DOMAIN}
authentication_method = token
token = ${FRP_TOKEN}
EOF

# 9. Build Caddy with Netlify DNS plugin
go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
xcaddy build --with github.com/caddy-dns/netlify
mv caddy /usr/local/bin/

# 10. Generate Caddyfile
cat > /etc/caddy/Caddyfile << EOF
{
    email admin@${DOMAIN}
    acme_dns netlify {env.NETLIFY_TOKEN}
}
*.${DOMAIN}, ${DOMAIN} {
    tls { dns netlify {env.NETLIFY_TOKEN} }
    reverse_proxy localhost:80
}
EOF

# 11. Create OpenRC services and start
rc-update add tunnel-admin default
rc-update add frps default
rc-update add caddy default
rc-service tunnel-admin start
rc-service frps start
rc-service caddy start

# 12. Configure firewall
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 7000/tcp
ufw --force enable

echo "Bootstrap complete!"
```

See `scripts/vultr-startup.sh` for the complete, production-ready implementation.

---

## 1Password Vault Structure

The service account needs read access to vault "Tunnel":

```
Vault: Tunnel
Item: tunnel-server
Fields:
  - jwt-secret        # JWT signing key
  - admin-password    # Admin dashboard password
  - admin-token       # Admin tunnel token
  - frp-token         # frp authentication token
  - netlify-token     # Netlify API token (for DNS)
  - domain            # Server domain
  - dash-password     # Optional: frp dashboard password
```

---

## Quick Reference

| What | Where | How |
|------|-------|-----|
| 1Password vault | "Tunnel" | Create at my.1password.com |
| JWT secret | `op://Tunnel/tunnel-server/jwt-secret` | `op read` |
| Admin password | `op://Tunnel/tunnel-server/admin-password` | `op read` |
| frp token | `op://Tunnel/tunnel-server/frp-token` | `op read` |
| Netlify token | `op://Tunnel/tunnel-server/netlify-token` | `op read` |
| Domain | `op://Tunnel/tunnel-server/domain` | `op read` |

---

## Verification Checklist

After bootstrap, verify:

- [ ] `rc-service tunnel-admin status` shows running
- [ ] `rc-service frps status` shows running
- [ ] `rc-service caddy status` shows running
- [ ] `netstat -tlnp | grep 7000` shows frps listening
- [ ] `netstat -tlnp | grep 8000` shows tunnel-admin listening
- [ ] `netstat -tlnp | grep 443` shows caddy listening
- [ ] DNS records point to this server's public IP
- [ ] `curl https://yourdomain.com` works with valid TLS
- [ ] Admin dashboard accessible at `https://yourdomain.com:8000`
