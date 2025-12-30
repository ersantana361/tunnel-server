# Quick Start Guide

Get your self-hosted tunnel server running in 10 minutes.

## Prerequisites

- A server (VPS/cloud instance) with a public IP
- Domain name (optional, can use IP for testing)
- 1Password account (recommended for secrets management)

## Step 0: Set Up 1Password Secrets (Optional, 2 min)

```bash
# Install 1Password CLI
brew install 1password-cli  # macOS

# Generate and save secrets to 1Password
./scripts/setup-1password.sh

# Create a service account at https://my.1password.com
# → Developer Tools → Service Accounts
# Grant access to "Tunnel" vault, copy the token
```

## Step 1: Deploy Server (3 min)

**Option A: Vultr with 1Password (Recommended)**

```bash
# Edit scripts/vultr-startup.sh and paste your service account token:
# OP_SERVICE_ACCOUNT_TOKEN='ops_your_token_here'

# Then in Vultr:
# 1. Products → Startup Scripts → Add Startup Script
# 2. Paste contents of vultr-startup.sh
# 3. Deploy new Alpine Linux instance with the script selected
```

**Option B: Manual Deployment**

```bash
# Set up SSH key for password-free access (one-time)
ssh-copy-id root@YOUR_SERVER_IP

# Deploy from your local machine
export TUNNEL_SERVER_IP=YOUR_SERVER_IP
./scripts/deploy.sh

# SSH into server and run installer
ssh root@YOUR_SERVER_IP
cd /opt/tunnel-server
sudo ./scripts/install.sh
```

**Credentials are stored in 1Password** (vault: `Tunnel`, item: `tunnel-server`)

## Step 2: Configure DNS (2 min)

For subdomain-based tunnels, add these DNS records:

```
Type    Name    Value
A       @       YOUR_SERVER_IP
A       *       YOUR_SERVER_IP
```

Then configure the server:

```bash
# On your server
sed -i 's/subdomain_host.*/subdomain_host = yourdomain.com/' /etc/frp/frps.ini
rc-service frps restart  # Alpine
# or: systemctl restart frps  # Ubuntu/Debian
```

## Step 3: Create a User (2 min)

1. Open admin dashboard: `http://YOUR_SERVER_IP:8000`
2. Login with admin credentials
3. Click "Users" tab
4. Click "Create User"
   - Email: `your-email@example.com`
   - Password: `your-password`
   - Max Tunnels: `10`
5. **Copy the tunnel token** - you'll need this next

## Step 4: Install frpc Client (2 min)

On your local machine, download frp:

```bash
# Download from https://github.com/fatedier/frp/releases
# Example for Linux amd64:
wget https://github.com/fatedier/frp/releases/download/v0.51.3/frp_0.51.3_linux_amd64.tar.gz
tar -xzf frp_0.51.3_linux_amd64.tar.gz
cd frp_0.51.3_linux_amd64
```

## Step 5: Create Tunnel Config (1 min)

Create `frpc.ini`:

```ini
[common]
server_addr = yourdomain.com
server_port = 7000
token = YOUR_USER_TOKEN_FROM_STEP_3

[my-app]
type = http
local_ip = 127.0.0.1
local_port = 3000
subdomain = myapp
```

## Step 6: Connect (30 sec)

```bash
# Start a local service (example)
python3 -m http.server 3000 &

# Connect the tunnel
./frpc -c frpc.ini
```

Now access your local service at: `http://myapp.yourdomain.com`

## Done!

You now have:
- Admin dashboard at `http://YOUR_SERVER_IP:8000`
- Tunnel server accepting connections on port 7000
- Your local port 3000 exposed via `myapp.yourdomain.com`

## Common Tunnel Examples

### Web Application
```ini
[webapp]
type = http
local_ip = 127.0.0.1
local_port = 3000
subdomain = app
```
Access at: `http://app.yourdomain.com`

### API Server
```ini
[api]
type = http
local_ip = 127.0.0.1
local_port = 8080
subdomain = api
```
Access at: `http://api.yourdomain.com`

### Database (TCP)
```ini
[postgres]
type = tcp
local_ip = 127.0.0.1
local_port = 5432
remote_port = 5432
```
Connect: `psql -h yourdomain.com -p 5432`

### Multiple Tunnels
```ini
[common]
server_addr = yourdomain.com
server_port = 7000
token = YOUR_TOKEN

[frontend]
type = http
local_ip = 127.0.0.1
local_port = 3000
subdomain = app

[backend]
type = http
local_ip = 127.0.0.1
local_port = 8080
subdomain = api
```

## Troubleshooting

### Can't access admin dashboard?
```bash
# Check service status
systemctl status tunnel-admin  # Ubuntu/Debian
rc-service tunnel-admin status  # Alpine

# Check logs
journalctl -u tunnel-admin -n 50
```

### frpc won't connect?
- Check server URL format: `yourdomain.com` (not http://)
- Verify port 7000 is accessible: `telnet yourdomain.com 7000`
- Verify token matches your user's token

### Tunnel shows "page not found"?
- Ensure your local service is running on the specified port
- Check frpc output for errors
- Verify subdomain_host is configured in frps.ini

## Next Steps

- [Full Documentation](docs/README.md)
- [API Reference](docs/api/README.md)
- [Security Guide](docs/security/README.md)
