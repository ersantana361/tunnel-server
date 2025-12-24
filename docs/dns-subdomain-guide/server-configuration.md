# Complete Server Configuration Guide for Subdomains

## Overview

You'll configure your server so that:
- `api.tunnel.yourdomain.com` -> localhost:8080 (on client)
- `app.tunnel.yourdomain.com` -> localhost:3000 (on client)
- `staging.tunnel.yourdomain.com` -> localhost:8081 (on client)

## Prerequisites Checklist

```bash
[ ] DNS configured in Netlify:
  - tunnel.yourdomain.com -> YOUR_VULTR_IP
  - *.tunnel.yourdomain.com -> YOUR_VULTR_IP

[ ] Server running (Vultr Sao Paulo)

[ ] Server installed with tunnel-server
```

## Step 1: Configure frps (Server Side)

### SSH into your server

```bash
ssh root@YOUR_VULTR_IP
```

### Edit frps configuration

```bash
nano /etc/frp/frps.ini
```

### Update the configuration

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = tunnel.yourdomain.com

# Logging
log_file = /var/log/frps.log
log_level = info

# Connection limits
max_pool_count = 5
```

**Key line:** `subdomain_host = tunnel.yourdomain.com`

### Restart frps

```bash
systemctl restart frps
systemctl status frps
```

**Expected output:**
```
frps.service - frp server
   Loaded: loaded (/etc/systemd/system/frps.service; enabled)
   Active: active (running) since...
```

## Step 2: Verify DNS Configuration

### Test DNS from your local machine

```bash
# Test base subdomain
dig tunnel.yourdomain.com

# Expected output should include:
# tunnel.yourdomain.com.  300  IN  A  YOUR_VULTR_IP

# Test wildcard
dig api.tunnel.yourdomain.com
dig app.tunnel.yourdomain.com

# All should return: YOUR_VULTR_IP
```

### Using nslookup (alternative)

```bash
nslookup tunnel.yourdomain.com
nslookup api.tunnel.yourdomain.com
```

### Online DNS checker

Visit: https://www.whatsmydns.net/
- Enter: `tunnel.yourdomain.com`
- Type: A
- Should show your Vultr IP globally

**Note:** DNS propagation can take 5-30 minutes

## Step 3: Configure Admin Dashboard

### Restart admin service

```bash
systemctl restart tunnel-admin
systemctl status tunnel-admin
```

### Access admin dashboard

```bash
http://YOUR_VULTR_IP:8000
```

Login and verify you can create users.

## Step 4: Client Configuration

### On the client machine

```bash
# Start the client application
cd tunnel-client-v2
python3 app.py
```

### Access client UI

```
http://localhost:3000
```

### Connect to server

```
Server URL: http://YOUR_VULTR_IP:7000
Token: [YOUR_TOKEN_FROM_ADMIN]
```

Click **"Connect"**

### Create your first tunnel

```
Name: api
Type: HTTP
Local Port: 8080
Subdomain: api
```

Click **"Add Tunnel"**

The system will generate the config:
```ini
[api]
type = http
local_ip = 127.0.0.1
local_port = 8080
subdomain = api
```

This creates: `api.tunnel.yourdomain.com` -> `localhost:8080`

### Start the tunnel service

Click **"Start"** button in the UI

## Step 5: Test the Setup

### Start a test service on client

```bash
# Terminal on your client machine
python3 -m http.server 8080
```

### Test the tunnel

```bash
# From any machine (or browser)
curl http://api.tunnel.yourdomain.com

# Or open in browser:
http://api.tunnel.yourdomain.com
```

**Expected:** You should see the directory listing from your http.server

### Test multiple tunnels

**Create second tunnel:**
```
Name: app
Type: HTTP
Local Port: 3000
Subdomain: app
```

**Start another service:**
```bash
# In another terminal
cd /path/to/your/react/app
npm start  # Runs on port 3000
```

**Access:**
```
http://app.tunnel.yourdomain.com
```

## Step 6: Verify Everything Works

### Check server logs

```bash
# On server
journalctl -u frps -f
```

**You should see:**
```
[control.go:xxx] [info] new proxy [api] success
```

### Check client logs

```bash
# On client
journalctl -u tunnel-client -f
```

**You should see:**
```
[control.go:xxx] start proxy success
```

### Test from different devices

```bash
# From your phone/tablet/another computer
http://api.tunnel.yourdomain.com
http://app.tunnel.yourdomain.com
```

All should work!

## How It Works (Visual)

```
User Request:
http://api.tunnel.yourdomain.com
          |
          v
DNS Resolution:
api.tunnel.yourdomain.com -> YOUR_VULTR_IP
          |
          v
Hits Vultr Server Port 80:
frps receives request
          |
          v
frps reads Host header:
Host: api.tunnel.yourdomain.com
          |
          v
frps looks up:
Which client registered subdomain "api"?
          |
          v
Finds:
Client from user@example.com
Tunnel: api -> localhost:8080
          |
          v
frps forwards request to:
Client's localhost:8080
          |
          v
Client responds
          |
          v
frps sends response back to user
```

## Complete Working Example

### DNS Setup (Netlify)

```
Type    Name                Value           TTL
A       tunnel              159.89.123.45   Auto
A       *.tunnel            159.89.123.45   Auto
```

### Server Config (/etc/frp/frps.ini)

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = tunnel.yourdomain.com
log_file = /var/log/frps.log
log_level = info
max_pool_count = 5
```

### Client 1 Tunnels

```
Tunnel: api
Type: HTTP
Port: 8080
Subdomain: api
-> Creates: api.tunnel.yourdomain.com
```

### Client 2 Tunnels (different user)

```
Tunnel: staging
Type: HTTP
Port: 3000
Subdomain: staging
-> Creates: staging.tunnel.yourdomain.com
```

### Result

```
http://api.tunnel.yourdomain.com -> Client 1's localhost:8080
http://staging.tunnel.yourdomain.com -> Client 2's localhost:3000
```

## Troubleshooting

### Issue: DNS not resolving

**Check:**
```bash
dig tunnel.yourdomain.com
```

**Solutions:**
1. Wait 30 minutes for DNS propagation
2. Verify Netlify DNS settings
3. Clear local DNS cache:
   ```bash
   # macOS
   sudo dscacheutil -flushcache

   # Linux
   sudo systemd-resolve --flush-caches

   # Windows
   ipconfig /flushdns
   ```

### Issue: Connection refused on port 7000

**Check frps is running:**
```bash
systemctl status frps
```

**Check firewall:**
```bash
ufw status | grep 7000
```

**Test port:**
```bash
telnet YOUR_VULTR_IP 7000
```

**Solution:**
```bash
# Open port in firewall
ufw allow 7000/tcp
systemctl restart frps
```

### Issue: Subdomain returns 404

**Check frps logs:**
```bash
journalctl -u frps -n 50
```

**Verify tunnel is active:**
```bash
# In admin dashboard
http://YOUR_VULTR_IP:8000
# Go to Tunnels tab
# Verify tunnel shows "Connected"
```

**Check client is connected:**
```bash
# In client UI
http://localhost:3000
# Status should show: Connected (PID: xxxx)
```

### Issue: "Subdomain already in use"

**Cause:** Another user is using the same subdomain

**Solution:** Choose a different subdomain
```
Instead of: api
Try: api-v2, myapi, api-prod, etc.
```

## Quick Reference

### Server Files

```
Configuration: /etc/frp/frps.ini
Service: /etc/systemd/system/frps.service
Logs: /var/log/frps.log
Admin Entry: /opt/tunnel-server/main.py
Admin App: /opt/tunnel-server/app/
Database: /var/lib/tunnel-server/tunnel.db
```

### Server Commands

```bash
# View logs
journalctl -u frps -f
journalctl -u tunnel-admin -f

# Restart services
systemctl restart frps
systemctl restart tunnel-admin

# Check status
systemctl status frps
systemctl status tunnel-admin

# Edit config
nano /etc/frp/frps.ini
```

### Client Files

```
Configuration: /etc/frp/frpc.ini (auto-generated)
Service: /etc/systemd/system/tunnel-client.service
Database: ./tunnel_client.db
```

### Client Commands

```bash
# Start manually
python3 app.py

# Or as service
systemctl start tunnel-client
systemctl status tunnel-client

# View logs
journalctl -u tunnel-client -f
```

## Final Checklist

```bash
Server:
[ ] frps.ini has correct subdomain_host
[ ] frps service is running
[ ] Admin dashboard accessible
[ ] Port 7000 open in firewall
[ ] Port 80 open in firewall
[ ] Port 8000 open in firewall

DNS:
[ ] tunnel.yourdomain.com -> YOUR_IP
[ ] *.tunnel.yourdomain.com -> YOUR_IP
[ ] DNS propagated (check whatsmydns.net)

Client:
[ ] Client connected to server
[ ] Tunnel created with subdomain
[ ] Local service running on specified port
[ ] Tunnel service started

Test:
[ ] http://subdomain.tunnel.yourdomain.com works
[ ] Can access from different devices
[ ] Multiple tunnels work simultaneously
```

## Next Steps

Once everything is working:

1. **Add HTTPS** (optional but recommended)
2. **Create more users** in admin dashboard
3. **Set up monitoring** (view logs, stats)
4. **Configure backups** for the database
5. **Restrict admin dashboard** to your IP only
