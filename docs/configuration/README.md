# Configuration

Complete guide to configuring the Tunnel Server for development and production environments.

## Table of Contents

- [Environment Variables](#environment-variables)
- [1Password Integration](#1password-integration)
- [Application Configuration](#application-configuration)
- [Database Configuration](#database-configuration)
- [frp Server Configuration](#frp-server-configuration)
- [Network Configuration](#network-configuration)
- [Development vs Production](#development-vs-production)
- [Netlify DNS Configuration](#netlify-dns-configuration)

---

## Environment Variables

The application is configured primarily through environment variables, allowing different settings per environment without code changes.

### Available Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET` | Secret key for JWT token signing | Auto-generated (32 bytes hex) | No |
| `DB_PATH` | Path to SQLite database file | `./tunnel.db` | No |
| `FRPS_CONFIG` | Path to frp server config | `/etc/frp/frps.ini` | No |
| `ADMIN_PASSWORD` | Admin password (from 1Password) | Auto-generated | No |
| `ADMIN_TOKEN` | Admin tunnel token (from 1Password) | Auto-generated | No |
| `OP_SERVICE_ACCOUNT_TOKEN` | 1Password service account token | None | For production |
| `NETLIFY_API_TOKEN` | Netlify API token for automatic DNS | None | For auto DNS |
| `NETLIFY_DNS_ZONE_ID` | Netlify DNS zone ID (auto-detected if not set) | Auto-detected | No |
| `TUNNEL_DOMAIN` | Domain for tunnel DNS records | `tunnel.ersantana.com` | No |
| `FRPS_DASHBOARD_HOST` | frps dashboard hostname | `localhost` | No |
| `FRPS_DASHBOARD_PORT` | frps dashboard port | `7500` | No |
| `FRPS_DASHBOARD_USER` | frps dashboard username | `admin` | No |
| `FRPS_DASHBOARD_PASS` | frps dashboard password | Empty | For metrics |

### Setting Environment Variables

#### Linux/macOS (Temporary)

```bash
# Single command
JWT_SECRET=my-secret-key python3 main.py

# Export for session
export JWT_SECRET=my-secret-key
export DB_PATH=/var/lib/tunnel-server/tunnel.db
python3 main.py
```

#### Linux/macOS (Permanent)

```bash
# Add to ~/.bashrc or ~/.zshrc
export JWT_SECRET=my-secret-key
export DB_PATH=/var/lib/tunnel-server/tunnel.db

# Reload
source ~/.bashrc
```

#### Using .env File (Recommended for Development)

Create a `.env` file in the project root:

```env
JWT_SECRET=your-secret-key-here
DB_PATH=./tunnel.db
FRPS_CONFIG=/etc/frp/frps.ini
```

**Note**: The application uses `python-dotenv` (included via uvicorn[standard]) which automatically loads `.env` files.

#### Systemd Service (Production)

In the systemd service file:

```ini
[Service]
Environment="JWT_SECRET=your-production-secret"
Environment="DB_PATH=/var/lib/tunnel-server/tunnel.db"
```

---

## 1Password Integration

The recommended way to manage secrets is using 1Password CLI (`op`).

### Setup

```bash
# 1. Install 1Password CLI
# macOS: brew install 1password-cli
# Linux: https://developer.1password.com/docs/cli/get-started

# 2. Generate secrets and save to 1Password
./scripts/setup-1password.sh
```

This creates a `tunnel-server` item in the `Tunnel` vault with:
- `jwt-secret` - JWT signing key
- `admin-password` - Admin dashboard password
- `admin-token` - Admin tunnel token
- `frp-token` - frp authentication token
- `domain` - Server domain
- `dash-password` - (optional) frp dashboard password
- `netlify-token` - (optional) For automatic DNS record creation (zone ID is auto-detected)

### Using .env.1password

The `.env.1password` file contains `op://` references:

```env
JWT_SECRET=op://Tunnel/tunnel-server/jwt-secret
ADMIN_PASSWORD=op://Tunnel/tunnel-server/admin-password
ADMIN_TOKEN=op://Tunnel/tunnel-server/admin-token
DB_PATH=/var/lib/tunnel-server/tunnel.db

# Netlify DNS (for automatic DNS record creation on startup)
# Only the API token is required - zone ID is auto-detected from the domain
NETLIFY_API_TOKEN=op://Tunnel/tunnel-server/netlify-token
TUNNEL_DOMAIN=tunnel.ersantana.com
```

### Running with 1Password

**Development (interactive):**

```bash
op run --env-file=.env.1password -- python3 main.py
```

**Using the wrapper script:**

```bash
./scripts/start.sh
```

**Production (service account):**

```bash
export OP_SERVICE_ACCOUNT_TOKEN="ops_your_token_here"
op run --env-file=.env.1password -- python3 main.py
```

### OpenRC Service (Alpine)

The install script creates an OpenRC service that uses 1Password:

```sh
#!/sbin/openrc-run

name="tunnel-server"
description="Tunnel Server Admin Dashboard"
command="/opt/tunnel-server/scripts/start.sh"
command_background=true
pidfile="/run/${RC_SVCNAME}.pid"

start_pre() {
    # Source 1Password token
    if [ -f /etc/profile.d/1password.sh ]; then
        . /etc/profile.d/1password.sh
    fi
}
```

---

## Application Configuration

### JWT Settings

Located in `app/config.py`:

```python
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

| Setting | Value | Description |
|---------|-------|-------------|
| `SECRET_KEY` | 64-char hex | Key for signing JWTs |
| `ALGORITHM` | HS256 | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Token validity period |

#### Customizing Token Expiration

To change token lifetime, modify `ACCESS_TOKEN_EXPIRE_MINUTES`:

```python
# 1 hour tokens
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# 8 hour tokens (for less frequent re-authentication)
ACCESS_TOKEN_EXPIRE_MINUTES = 480

# 24 hour tokens
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
```

**Security Consideration**: Longer token lifetimes are less secure. If a token is compromised, it remains valid until expiration.

### Server Settings

The uvicorn server is configured in `main.py`:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

| Setting | Default | Description |
|---------|---------|-------------|
| `host` | 0.0.0.0 | Listen on all interfaces |
| `port` | 8000 | HTTP port |

#### Customizing Server Settings

```python
# Listen only on localhost
uvicorn.run(app, host="127.0.0.1", port=8000)

# Custom port
uvicorn.run(app, host="0.0.0.0", port=9000)

# With reload for development
uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

# Multiple workers for production
uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)
```

---

## Database Configuration

### Path Configuration

The database path is configured via the `DB_PATH` environment variable:

```python
DB_FILE = os.getenv("DB_PATH", "./tunnel.db")
```

#### Common Configurations

| Environment | Path | Command |
|-------------|------|---------|
| Development | `./tunnel.db` | `python3 main.py` |
| Production | `/var/lib/tunnel-server/tunnel.db` | `DB_PATH=/var/lib/tunnel-server/tunnel.db python3 main.py` |
| Testing | `/tmp/test_tunnel.db` | `DB_PATH=/tmp/test_tunnel.db python3 main.py` |

### Database Initialization

On first run, the application automatically:

1. Creates the directory structure (if permissions allow)
2. Creates the SQLite database file
3. Creates all required tables
4. Generates a default admin account

```python
def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    # ... table creation
```

### Database Permissions

Ensure the application has write access to the database path:

```bash
# Create directory with proper permissions
sudo mkdir -p /var/lib/tunnel-server
sudo chown $USER:$USER /var/lib/tunnel-server

# Or for a service user
sudo chown www-data:www-data /var/lib/tunnel-server
```

### Database Backup

```bash
# Simple backup
cp /var/lib/tunnel-server/tunnel.db /backup/tunnel_$(date +%Y%m%d).db

# With sqlite3 backup command (safer for live databases)
sqlite3 /var/lib/tunnel-server/tunnel.db ".backup '/backup/tunnel_backup.db'"
```

---

## frp Server Configuration

### Configuration File

The frp server configuration is typically stored at `/etc/frp/frps.ini`:

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = yourdomain.com

# Logging
log_file = /var/log/frps.log
log_level = info

# Connection limits
max_pool_count = 5
```

### Configuration Options

| Option | Description | Example |
|--------|-------------|---------|
| `bind_port` | Control channel port | 7000 |
| `vhost_http_port` | HTTP tunnel port | 80 |
| `vhost_https_port` | HTTPS tunnel port | 443 |
| `subdomain_host` | Base domain for subdomains | example.com |
| `log_file` | Log file path | /var/log/frps.log |
| `log_level` | Logging verbosity | info, debug, warn, error |
| `max_pool_count` | Max connections per tunnel | 5 |

### Token Authentication

To integrate with the admin app's token system, configure frp to use token authentication:

```ini
[common]
bind_port = 7000
authentication_method = token
authenticate_heartbeats = true
authenticate_new_work_conns = true
```

### Custom Port Ranges

For TCP tunnels, you can restrict available ports:

```ini
[common]
bind_port = 7000
allow_ports = 5000-6000,8080,9000-9100
```

### frps Dashboard (for Metrics)

The tunnel server can collect aggregate metrics from the frps dashboard API. Configure the frps web dashboard:

```toml
# /etc/frp/frps.toml
[webServer]
addr = "0.0.0.0"
port = 7500
user = "admin"
password = "your-dashboard-password"
```

Then configure the tunnel server to connect:

```bash
export FRPS_DASHBOARD_HOST=localhost
export FRPS_DASHBOARD_PORT=7500
export FRPS_DASHBOARD_USER=admin
export FRPS_DASHBOARD_PASS=your-dashboard-password
```

The server will poll the frps dashboard every 60 seconds to collect:
- Traffic statistics per tunnel
- Connection counts
- Online/offline status

---

## Network Configuration

### Firewall Rules (UFW)

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Admin dashboard
sudo ufw allow 8000/tcp

# frp control port
sudo ufw allow 7000/tcp

# HTTP/HTTPS tunnels
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

### Firewall Rules (iptables)

```bash
# Admin dashboard
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

# frp ports
iptables -A INPUT -p tcp --dport 7000 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Nginx Reverse Proxy (Optional)

To serve the admin dashboard through Nginx:

```nginx
server {
    listen 80;
    server_name admin.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### SSL/TLS with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d admin.yourdomain.com

# Auto-renewal is configured automatically
```

---

## Development vs Production

### Configuration Comparison

| Setting | Development | Production |
|---------|-------------|------------|
| `DB_PATH` | `./tunnel.db` | `/var/lib/tunnel-server/tunnel.db` |
| `JWT_SECRET` | Auto-generated | Fixed, secure value |
| Host | `0.0.0.0` or `127.0.0.1` | `0.0.0.0` behind proxy |
| Workers | 1 | 2-4 |
| Debug | Enabled | Disabled |
| HTTPS | Optional | Required |

### Development Configuration

```bash
# Quick start for development
python3 main.py

# Or with auto-reload
uvicorn main:app --reload
```

Or with explicit settings:

```bash
DB_PATH=./dev_tunnel.db \
JWT_SECRET=dev-secret-not-for-production \
python3 main.py
```

### Production Configuration

**Systemd Service File** (`/etc/systemd/system/tunnel-admin.service`):

```ini
[Unit]
Description=Tunnel Server Admin Dashboard
After=network.target

[Service]
Type=simple
User=tunnel-admin
Group=tunnel-admin
WorkingDirectory=/opt/tunnel-server
ExecStart=/usr/bin/python3 /opt/tunnel-server/main.py
Restart=on-failure
RestartSec=5s
Environment="JWT_SECRET=your-very-secure-secret-key-here"
Environment="DB_PATH=/var/lib/tunnel-server/tunnel.db"

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/tunnel-server

[Install]
WantedBy=multi-user.target
```

### Configuration Checklist

#### Development
- [ ] Python 3.8+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created (optional)
- [ ] Port 8000 available

#### Production
- [ ] Dedicated server or VM
- [ ] Non-root user created for service
- [ ] Firewall configured
- [ ] JWT_SECRET set to secure value
- [ ] Database path with proper permissions
- [ ] Systemd service configured
- [ ] SSL/TLS configured (recommended)
- [ ] Backup strategy in place
- [ ] Monitoring configured

---

## Quick Reference

### Environment Variable Summary

```bash
# All available environment variables with examples
export JWT_SECRET="your-64-character-hex-secret-key-here"
export DB_PATH="/var/lib/tunnel-server/tunnel.db"
export FRPS_CONFIG="/etc/frp/frps.ini"

# Netlify DNS (optional - for automatic DNS record creation)
# Zone ID is auto-detected from the domain
export NETLIFY_API_TOKEN="your-netlify-api-token"
export TUNNEL_DOMAIN="tunnel.ersantana.com"
```

---

## Netlify DNS Configuration

The server can automatically create and update DNS records on startup using the Netlify API.

### How It Works

On startup, the server:
1. Detects its public IP address
2. Auto-detects the DNS zone ID from `TUNNEL_DOMAIN` (e.g., finds zone for `ersantana.com` from `tunnel.ersantana.com`)
3. Creates/updates an A record for `tunnel.ersantana.com`
4. Creates/updates a wildcard A record for `*.tunnel.ersantana.com`

If records already exist with the correct IP, no changes are made.

### Configuration

Only the API token and domain are required - the zone ID is auto-detected:

```env
NETLIFY_API_TOKEN=op://Tunnel/tunnel-server/netlify-token
TUNNEL_DOMAIN=tunnel.ersantana.com
```

You can optionally set `NETLIFY_DNS_ZONE_ID` to skip auto-detection if needed.

### Disabling Automatic DNS

To disable automatic DNS, simply don't set `NETLIFY_API_TOKEN`. The server will skip DNS setup and log a message.

### Configuration File Locations

| File | Development | Production |
|------|-------------|------------|
| Entry Point | `./main.py` | `/opt/tunnel-server/main.py` |
| Application | `./app/` | `/opt/tunnel-server/app/` |
| Database | `./tunnel.db` | `/var/lib/tunnel-server/tunnel.db` |
| frp Config | N/A | `/etc/frp/frps.ini` |
| Service File | N/A | `/etc/systemd/system/tunnel-admin.service` |
| Logs | Console | `journalctl -u tunnel-admin` |

---

## Related Documentation

- [Getting Started](../getting-started/README.md) - Initial setup
- [Deployment](../deployment/README.md) - Production deployment
- [Security](../security/README.md) - Security configuration
- [Troubleshooting](../troubleshooting/README.md) - Common issues
