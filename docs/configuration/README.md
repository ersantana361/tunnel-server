# Configuration

Complete guide to configuring the Tunnel Server for development and production environments.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Application Configuration](#application-configuration)
- [Database Configuration](#database-configuration)
- [frp Server Configuration](#frp-server-configuration)
- [Network Configuration](#network-configuration)
- [Development vs Production](#development-vs-production)

---

## Environment Variables

The application is configured primarily through environment variables, allowing different settings per environment without code changes.

### Available Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET` | Secret key for JWT token signing | Auto-generated (32 bytes hex) | No |
| `DB_PATH` | Path to SQLite database file | `./tunnel.db` | No |
| `FRPS_CONFIG` | Path to frp server config | `/etc/frp/frps.ini` | No |

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
```

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
