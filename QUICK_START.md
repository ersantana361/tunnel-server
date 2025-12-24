# Quick Start Guide - 10 Minutes to Your Own ngrok

This guide will have you running your own tunnel service in 10 minutes.

## Prerequisites

- DigitalOcean account ($4/month droplet)
- Domain name (optional, can use IP)
- SSH access to your server

## Step 1: Create DigitalOcean Droplet (2 min)

1. Go to DigitalOcean
2. Create Droplet:
   - **OS**: Ubuntu 24.04 LTS
   - **Plan**: Basic $4/month (1GB RAM)
   - **Region**: Closest to you
   - **Add SSH key**
3. Wait for it to boot (~60 seconds)
4. Note the IP address

## Step 2: Install Server (3 min)

```bash
# Set up SSH key for password-free access (one-time)
ssh-copy-id root@YOUR_DROPLET_IP

# Deploy from your local machine
export TUNNEL_SERVER_IP=YOUR_DROPLET_IP
./scripts/deploy.sh

# SSH into your server for first-time install
ssh root@YOUR_DROPLET_IP
cd /opt/tunnel-server
chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

**IMPORTANT**: Save the admin credentials shown at the end!

Example output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADMIN CREDENTIALS - SAVE THESE!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Email: admin@localhost
Password: abc123xyz789...
Token: def456uvw012...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Step 3: Create a User (2 min)

1. Open admin dashboard: `http://YOUR_SERVER_IP:8000`
2. Login with admin credentials
3. Click "Users" tab
4. Click "Create User"
   - Email: `your-email@example.com`
   - Password: `your-password`
   - Max Tunnels: `10`
5. Click "Create User"
6. **Copy the tunnel token shown** - you'll need this for the client

## Step 4: Install Client (2 min)

On your local machine:

```bash
cd tunnel-client-v2

# Install dependencies
chmod +x install.sh
./install.sh

# Start the client
python3 app.py
```

## Step 5: Connect & Create Tunnel (1 min)

1. Open: `http://localhost:3000`
2. Enter configuration:
   - **Server URL**: `http://YOUR_SERVER_IP:7000`
   - **Your Token**: (paste from step 3)
3. Click "Connect"
4. Add your first tunnel:
   - **Name**: `my-api`
   - **Type**: `HTTP`
   - **Local Port**: `8080` (or whatever you're running)
   - **Subdomain**: `api`
5. Click "Add Tunnel"
6. Click "Start"

## Step 6: Test It! (30 sec)

```bash
# Start a simple web server
python3 -m http.server 8080
```

Now access it at:
- If using domain: `http://api.yourdomain.com`
- If using IP: `http://YOUR_SERVER_IP` (with proxy setup)

## 🎉 Done!

You now have:
- ✅ Admin dashboard to manage users
- ✅ Client dashboard to manage tunnels
- ✅ Secure token-based authentication
- ✅ Unlimited tunnels (within your limits)
- ✅ Real-time monitoring
- ✅ Full control over your data

## Common Use Cases

### Expose Your API
```
Name: api
Type: HTTP
Local Port: 8080
Subdomain: api
```
Access at: `api.yourdomain.com`

### Demo React App
```
Name: webapp
Type: HTTP
Local Port: 3000
Subdomain: demo
```
Access at: `demo.yourdomain.com`

### Share Database
```
Name: postgres
Type: TCP
Local Port: 5432
Remote Port: 5432
```
Connect: `psql -h YOUR_SERVER_IP -p 5432`

## Pro Tips

### Auto-start Client on Boot
```bash
sudo systemctl enable tunnel-client
sudo systemctl start tunnel-client
```

### Monitor Everything
- **Server**: `http://YOUR_SERVER_IP:8000`
- **Client**: `http://localhost:3000`
- **Logs**: `journalctl -u tunnel-client -f`

### Multiple Tunnels
Add as many as you want! Enable/disable with one click.

### Team Setup
Create a user for each team member, they each get their own token.

## Troubleshooting

### Can't access admin?
```bash
systemctl status tunnel-admin
journalctl -u tunnel-admin -n 50
```

### Client won't connect?
- Check server URL format: `http://server:7000` (not 8000!)
- Verify token is correct
- Test: `telnet YOUR_SERVER_IP 7000`

### Tunnel not working?
- Make sure service is running (green dot)
- Check your local service is running
- View logs in the client UI

## Next Steps

1. **Setup DNS** - Point `*.yourdomain.com` to your server
2. **Add HTTPS** - Setup Let's Encrypt (see server README)
3. **Create more users** - For your team
4. **Monitor usage** - Check activity logs

## Need Help?

- Full docs: See README-v2.md
- Server details: tunnel-server-v2/README.md
- Client details: tunnel-client-v2/README.md

---

**Total Time**: ~10 minutes
**Total Cost**: $4/month
**Total Value**: Priceless 😎
