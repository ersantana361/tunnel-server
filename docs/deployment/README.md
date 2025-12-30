# Deployment Guide

Complete guide for deploying the Tunnel Server to production environments.

## Table of Contents

- [Deployment Overview](#deployment-overview)
- [Server Requirements](#server-requirements)
- [Deployment with 1Password](#deployment-with-1password)
- [Automated Installation](#automated-installation)
- [Manual Installation](#manual-installation)
- [Systemd Services](#systemd-services)
- [SSL/TLS Configuration](#ssltls-configuration)
- [DNS Configuration](#dns-configuration)
- [Monitoring and Logging](#monitoring-and-logging)
- [Backup and Recovery](#backup-and-recovery)
- [Scaling Considerations](#scaling-considerations)

---

## Deployment Overview

The Tunnel Server consists of two main components that need to be deployed:

```
┌─────────────────────────────────────────────────────────┐
│                   Production Server                      │
│                                                          │
│   ┌─────────────────┐      ┌─────────────────────┐     │
│   │  tunnel-admin   │      │       frps          │     │
│   │  (Port 8000)    │      │   (Port 7000)       │     │
│   │                 │      │   (Port 80/443)     │     │
│   │  Python/FastAPI │      │   Go binary         │     │
│   └────────┬────────┘      └──────────┬──────────┘     │
│            │                          │                 │
│            └──────────┬───────────────┘                 │
│                       │                                 │
│              ┌────────▼────────┐                       │
│              │    SQLite DB    │                       │
│              │   tunnel.db     │                       │
│              └─────────────────┘                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Server Requirements

### Minimum Specifications

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 512 MB | 1 GB |
| Storage | 10 GB | 20 GB |
| OS | Ubuntu 20.04+ | Ubuntu 24.04 LTS |

### Recommended Cloud Providers

| Provider | Plan | Monthly Cost |
|----------|------|--------------|
| DigitalOcean | Basic Droplet | $4-6 |
| Linode | Nanode | $5 |
| Vultr | Cloud Compute | $5 |
| AWS | t3.micro | ~$8 |
| Hetzner | CX11 | €3.29 |

### Supported Operating Systems

| OS | Init System | Install Script |
|----|-------------|----------------|
| Alpine Linux 3.18+ | OpenRC | `scripts/install.sh` |

**Note**: The primary deployment target is Alpine Linux with 1Password integration.

### Required Software

- Python 3.8+
- pip
- SQLite3
- wget/curl
- OpenRC (Alpine)
- 1Password CLI (`op`)

---

## Deployment with 1Password

The recommended deployment method uses 1Password for secrets management.

### Prerequisites

1. **1Password Account** with service accounts enabled
2. **Vultr Account** (or other cloud provider)

### Step 1: Set Up Secrets Locally

```bash
# Install 1Password CLI
brew install 1password-cli  # macOS
# Or: https://developer.1password.com/docs/cli/get-started

# Generate secrets and save to 1Password
./scripts/setup-1password.sh
```

This creates a `tunnel-server` item in the `Tunnel` vault.

### Step 2: Create Service Account

1. Go to https://my.1password.com → **Developer Tools** → **Service Accounts**
2. Create a new service account (e.g., "tunnel-server")
3. Grant **Read & Write** access to the `Tunnel` vault
4. Copy the service account token (starts with `ops_`)

### Step 3: Configure Vultr Startup Script

Edit `scripts/vultr-startup.sh` and paste your token:

```bash
OP_SERVICE_ACCOUNT_TOKEN='ops_your_token_here'
```

### Step 4: Deploy to Vultr

1. Go to Vultr → **Products** → **Startup Scripts**
2. Create new startup script, paste contents of `vultr-startup.sh`
3. Deploy new Alpine Linux instance with the startup script selected

### What Gets Installed

The Vultr startup script automatically:
- Installs 1Password CLI
- Clones repository from GitHub
- Installs Python dependencies
- Configures frp server
- Sets up Caddy for SSL (if Netlify token provided)
- Creates OpenRC services
- Configures automatic DNS via Netlify API (if configured)
- Starts all services

### Verifying Deployment

```bash
ssh root@YOUR_SERVER_IP

# Check services
rc-service frps status
rc-service tunnel-server status
rc-service caddy status

# Check logs
tail -f /var/log/tunnel-bootstrap.log
```

---

## Automated Installation

The easiest way to deploy is using the provided installation script.

### Step 1: Upload Project Files

**Option 1: Using deploy script (recommended)**

```bash
# From your local machine
export TUNNEL_SERVER_IP=your-server-ip
./scripts/deploy.sh

# For password-free deploys, set up SSH keys first:
ssh-copy-id root@your-server-ip
```

**Option 2: Manual SCP**

```bash
# From your local machine
scp main.py requirements.txt root@your-server-ip:/opt/tunnel-server/
scp -r app root@your-server-ip:/opt/tunnel-server/
scp scripts/install-alpine.sh root@your-server-ip:/opt/tunnel-server/
```

**Option 3: Git clone on server**

```bash
ssh root@your-server-ip
git clone <repository-url> /opt/tunnel-server
```

### Step 2: Run Installation Script

**Ubuntu/Debian:**

```bash
cd /opt/tunnel-server
chmod +x install.sh
sudo ./install.sh
```

**Alpine Linux:**

```bash
cd /opt/tunnel-server
chmod +x install-alpine.sh
sudo ./install-alpine.sh
```

### Step 3: Save Credentials

The installation script outputs admin credentials:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADMIN CREDENTIALS - SAVE THESE!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Email: admin@localhost
Password: <random-password>
Token: <random-token>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Important**: Save these credentials immediately. They are only shown once.

---

## Manual Installation

For more control over the installation process.

### Step 1: System Updates

```bash
apt update && apt upgrade -y
```

### Step 2: Install Dependencies

```bash
apt install -y python3 python3-pip python3-venv sqlite3 wget tar ufw
```

### Step 3: Install frp Server

```bash
FRP_VERSION="0.52.3"
cd /tmp
wget https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz
tar -xzf frp_${FRP_VERSION}_linux_amd64.tar.gz
cp frp_${FRP_VERSION}_linux_amd64/frps /usr/local/bin/
chmod +x /usr/local/bin/frps
rm -rf /tmp/frp_*
```

### Step 4: Create Directories

```bash
mkdir -p /opt/tunnel-server
mkdir -p /var/lib/tunnel-server
mkdir -p /etc/frp
```

### Step 5: Configure frp Server

Create `/etc/frp/frps.ini`:

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = yourdomain.com

log_file = /var/log/frps.log
log_level = info

max_pool_count = 5
```

### Step 6: Install Python Dependencies

```bash
cd /opt/tunnel-server
pip3 install -r requirements.txt --break-system-packages
```

### Step 7: Copy Application

```bash
cp main.py /opt/tunnel-server/
cp -r app /opt/tunnel-server/
```

### Step 8: Configure Firewall

```bash
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP tunnels
ufw allow 443/tcp  # HTTPS tunnels
ufw allow 7000/tcp # frp control
ufw allow 8000/tcp # Admin dashboard
ufw --force enable
```

---

## Systemd Services

### frp Server Service

Create `/etc/systemd/system/frps.service`:

```ini
[Unit]
Description=frp server
After=network.target

[Service]
Type=simple
User=root
Restart=on-failure
RestartSec=5s
ExecStart=/usr/local/bin/frps -c /etc/frp/frps.ini
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

### Admin Dashboard Service

Create `/etc/systemd/system/tunnel-admin.service`:

```ini
[Unit]
Description=Tunnel Server Admin Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tunnel-server
ExecStart=/usr/bin/python3 /opt/tunnel-server/main.py
Restart=on-failure
RestartSec=5s
Environment="JWT_SECRET=your-secure-secret-here"
Environment="DB_PATH=/var/lib/tunnel-server/tunnel.db"

[Install]
WantedBy=multi-user.target
```

### Enable and Start Services

```bash
systemctl daemon-reload
systemctl enable frps tunnel-admin
systemctl start frps tunnel-admin
```

### Check Service Status

```bash
systemctl status frps
systemctl status tunnel-admin
```

---

## Alpine Linux (OpenRC)

Alpine uses OpenRC instead of systemd. The `install-alpine.sh` script handles this automatically.

### Service Management

```bash
# Start/stop/restart services
rc-service frps start
rc-service frps stop
rc-service frps restart

rc-service tunnel-admin start
rc-service tunnel-admin stop
rc-service tunnel-admin restart

# Check status
rc-service frps status
rc-service tunnel-admin status

# Enable at boot
rc-update add frps default
rc-update add tunnel-admin default

# Disable at boot
rc-update del frps default
rc-update del tunnel-admin default
```

### Log Files

```bash
# View logs
tail -f /var/log/frps.log
tail -f /var/log/tunnel-admin.log
tail -f /var/log/tunnel-boot.log  # Boot recovery log
```

### Firewall (UFW)

Alpine uses UFW for firewall management:

```bash
# View current rules
ufw status

# Allow a port
ufw allow 8000/tcp

# Deny a port
ufw deny 9000/tcp

# Delete a rule
ufw delete allow 9000/tcp

# Enable/disable firewall
ufw enable
ufw disable
```

**Required ports:**
- 22/tcp - SSH
- 80/tcp - HTTP tunnels
- 443/tcp - HTTPS tunnels
- 7000/tcp - frp control
- 8000/tcp - Admin dashboard

---

## SSL/TLS Configuration

### Option 1: Caddy (Automatic HTTPS)

Install Caddy:

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy
```

Configure Caddy (`/etc/caddy/Caddyfile`):

```
admin.yourdomain.com {
    reverse_proxy localhost:8000
}
```

### Option 2: Nginx + Let's Encrypt

Install packages:

```bash
apt install -y nginx certbot python3-certbot-nginx
```

Configure Nginx (`/etc/nginx/sites-available/tunnel-admin`):

```nginx
server {
    listen 80;
    server_name admin.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable site and get certificate:

```bash
ln -s /etc/nginx/sites-available/tunnel-admin /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
certbot --nginx -d admin.yourdomain.com
```

---

## DNS Configuration

### Automatic DNS (Recommended)

The server can automatically create and update DNS records on startup via Netlify API:

```
tunnel.ersantana.com     → SERVER_IP
*.tunnel.ersantana.com   → SERVER_IP (wildcard)
```

To enable, add these to 1Password (`Tunnel/tunnel-server`):
- `netlify-api-token` - Your Netlify personal access token
- `netlify-dns-zone-id` - Your DNS zone ID

Get your zone ID:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.netlify.com/api/v1/dns_zones | jq '.[] | {name, id}'
```

The server automatically detects its public IP and creates/updates records on each startup.

### Manual A Records

If not using automatic DNS, point your domain to your server's IP:

```
Type    Name      Value              TTL
A       tunnel    YOUR_SERVER_IP     300
A       *.tunnel  YOUR_SERVER_IP     300
A       admin     YOUR_SERVER_IP     300
```

### Explanation

| Record | Purpose |
|--------|---------|
| `tunnel → IP` | Main tunnel domain |
| `*.tunnel → IP` | Wildcard for tunnel subdomains |
| `admin → IP` | Admin dashboard subdomain |

### Verification

```bash
# Check DNS propagation
dig tunnel.yourdomain.com
dig admin.yourdomain.com
dig test.tunnel.yourdomain.com
```

---

## Monitoring and Logging

### View Service Logs

```bash
# Admin dashboard logs
journalctl -u tunnel-admin -f

# frp server logs
journalctl -u frps -f

# Last 100 lines
journalctl -u tunnel-admin -n 100

# Logs since specific time
journalctl -u tunnel-admin --since "1 hour ago"
```

### frp Log File

```bash
tail -f /var/log/frps.log
```

### System Resource Monitoring

```bash
# Check memory usage
free -h

# Check disk usage
df -h

# Check CPU usage
top

# Check network connections
netstat -tuln | grep -E '7000|8000|80|443'
```

### Health Check Script

Create `/opt/tunnel-server/health-check.sh`:

```bash
#!/bin/bash

# Check admin dashboard
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200"; then
    echo "Admin dashboard: OK"
else
    echo "Admin dashboard: FAIL"
    systemctl restart tunnel-admin
fi

# Check frps
if pgrep -x frps > /dev/null; then
    echo "frps: OK"
else
    echo "frps: FAIL"
    systemctl restart frps
fi
```

Add to crontab for periodic checks:

```bash
crontab -e
# Add line:
*/5 * * * * /opt/tunnel-server/health-check.sh >> /var/log/tunnel-health.log 2>&1
```

---

## Backup and Recovery

### Automated Backup Script

Create `/opt/tunnel-server/backup.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/var/backups/tunnel-server"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
sqlite3 /var/lib/tunnel-server/tunnel.db ".backup '$BACKUP_DIR/tunnel_$DATE.db'"

# Backup configuration
cp /etc/frp/frps.ini $BACKUP_DIR/frps_$DATE.ini

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

### Schedule Daily Backups

```bash
crontab -e
# Add line:
0 2 * * * /opt/tunnel-server/backup.sh >> /var/log/tunnel-backup.log 2>&1
```

### Recovery Procedure

```bash
# Stop services
systemctl stop tunnel-admin frps

# Restore database
cp /var/backups/tunnel-server/tunnel_YYYYMMDD.db /var/lib/tunnel-server/tunnel.db

# Restore frp config
cp /var/backups/tunnel-server/frps_YYYYMMDD.ini /etc/frp/frps.ini

# Start services
systemctl start frps tunnel-admin
```

---

## Scaling Considerations

### Current Limitations

| Component | Limitation | Impact |
|-----------|------------|--------|
| SQLite | Single-writer | Concurrent writes may queue |
| Single Process | One worker | CPU-bound on one core |
| Single Server | No redundancy | Single point of failure |

### Horizontal Scaling Options

#### Multiple Workers (Quick Win)

Modify the start command in `main.py`:

```python
uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)
```

Or use gunicorn:

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

#### Database Migration (Future)

For high-traffic deployments, migrate to PostgreSQL:

1. Export SQLite data
2. Set up PostgreSQL
3. Modify database connection code
4. Import data

#### Load Balancing (Future)

For multiple servers:

```
                    ┌─────────────┐
                    │   HAProxy   │
                    │   or Nginx  │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │  Server 1 │    │  Server 2 │    │  Server 3 │
    └───────────┘    └───────────┘    └───────────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │  PostgreSQL │
                    │  (Shared)   │
                    └─────────────┘
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Server provisioned with required specs
- [ ] SSH access configured
- [ ] Domain purchased and DNS configured
- [ ] Firewall rules planned

### Installation

- [ ] System updated
- [ ] Dependencies installed
- [ ] frp installed
- [ ] Application files deployed
- [ ] Python dependencies installed
- [ ] Systemd services created
- [ ] Firewall configured

### Post-Deployment

- [ ] Services running
- [ ] Admin credentials saved
- [ ] SSL/TLS configured
- [ ] DNS verified
- [ ] Backups configured
- [ ] Monitoring set up
- [ ] Test user created
- [ ] Test tunnel verified

---

## Related Documentation

- [Getting Started](../getting-started/README.md) - Initial setup
- [Configuration](../configuration/README.md) - Configuration options
- [Security](../security/README.md) - Security hardening
- [Troubleshooting](../troubleshooting/README.md) - Common issues
