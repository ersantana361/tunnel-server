# Self-Hosted Tunnel Service (ngrok Alternative)

A complete self-hosted tunnel solution with **admin dashboard**, **user management**, **monitoring**, and **security features** - just like ngrok but under your control.

## 🎯 Features

### Server Side (DigitalOcean)
- 🎛️ **Admin Dashboard** - Web interface at port 8000
- 👥 **User Management** - Create/manage users with individual tokens
- 📊 **Real-time Monitoring** - Track active tunnels, users, and connections
- 🔐 **Security** - JWT authentication, bcrypt password hashing
- 📝 **Activity Logs** - Full audit trail of all actions
- 🔑 **Token-based Auth** - Each user gets unique tunnel token
- 📈 **Statistics** - User quotas, tunnel limits, usage tracking

### Client Side (Your Machine)
- 🖥️ **Web UI** - Manage tunnels at localhost:3000
- ✅ **Easy Setup** - Just enter server URL and your token
- 🚀 **Quick Toggle** - Enable/disable tunnels with one click
- 📊 **Status Monitoring** - See connection status in real-time
- 💾 **Persistent Config** - Saves all settings locally
- 🔄 **Auto-restart** - Reconnects automatically on failure

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DIGITALOCEAN SERVER                       │
│                                                              │
│  ┌──────────────────────────┐  ┌─────────────────────────┐  │
│  │   Admin Dashboard        │  │   frp Server (frps)     │  │
│  │   Port 8000              │  │   Port 7000             │  │
│  │                          │  │                         │  │
│  │  - User Management       │  │   Handles tunnels:      │  │
│  │  - Create Users          │  │   - HTTP (port 80)      │  │
│  │  - Generate Tokens       │  │   - HTTPS (port 443)    │  │
│  │  - Monitor Activity      │  │   - TCP (custom ports)  │  │
│  │  - View Statistics       │  │                         │  │
│  └──────────────────────────┘  └─────────────────────────┘  │
│              │                            │                   │
│         [SQLite DB]                       │                   │
│    - Users & Tokens                       │                   │
│    - Activity Logs                        │                   │
│    - Statistics                           │                   │
└──────────────────────────────────────────────────────────────┘
                                  │
                                  │  Tunnel Connection
                                  │  (Token Auth)
                                  │
┌──────────────────────────────────────────────────────────────┐
│                      YOUR MACHINE                            │
│                                                              │
│  ┌──────────────────────────┐  ┌─────────────────────────┐  │
│  │   Client Dashboard       │  │   frp Client (frpc)     │  │
│  │   Port 3000              │  │                         │  │
│  │                          │  │   Connects to:          │  │
│  │  - Add/Remove Tunnels    │  │   localhost:8080        │  │
│  │  - Start/Stop Service    │  │   localhost:3000        │  │
│  │  - Configure Settings    │  │   localhost:5432        │  │
│  │  - Monitor Status        │  │   etc...                │  │
│  └──────────────────────────┘  └─────────────────────────┘  │
│              │                                                │
│         [SQLite DB]                                          │
│    - Tunnel Config                                           │
│    - Server Settings                                         │
└──────────────────────────────────────────────────────────────┘
```

## 💰 Cost Comparison

| Feature | Self-Hosted | ngrok Free | ngrok Pro |
|---------|-------------|------------|-----------|
| **Monthly Cost** | $4 | $0 | $20 |
| **Custom Domains** | ✅ Unlimited | ❌ | ✅ Limited |
| **Subdomains** | ✅ Unlimited | ❌ Random | ✅ Limited |
| **User Management** | ✅ | ❌ | ✅ |
| **Session Limits** | ✅ None | ❌ 2 hours | ✅ None |
| **Admin Dashboard** | ✅ | ❌ | ✅ |
| **Activity Logs** | ✅ | ❌ | ✅ |
| **Full Control** | ✅ | ❌ | ❌ |
| **No Data Limits** | ✅ | ❌ Limited | ✅ |

**You get ngrok Pro features for 1/5th the price!**

## 🚀 Quick Start

### Local Development (2 minutes)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 main.py

# Or with auto-reload for development
uvicorn main:app --reload

# Run tests
pytest
```

- Opens at http://localhost:8000
- Creates `./tunnel.db` in current directory
- Admin credentials printed to console on first run

### Production Setup (5 minutes)

```bash
# Set up SSH key for password-free deploys (one-time)
ssh-copy-id root@your-server-ip

# Deploy from local machine
export TUNNEL_SERVER_IP=your-server-ip
./scripts/deploy.sh

# First time only: SSH and run installer
ssh root@your-server-ip
cd /opt/tunnel-server

# Ubuntu/Debian
chmod +x scripts/install.sh
sudo ./scripts/install.sh

# Alpine Linux
chmod +x scripts/install-alpine.sh
sudo ./scripts/install-alpine.sh
```

**Save the admin credentials shown!**

### 2. Access Admin Dashboard

1. Open: `http://your-server-ip:8000`
2. Login with admin credentials
3. Create a user account
4. Copy the user's tunnel token

### 3. Setup Client (2 minutes)

```bash
# On your local machine
cd tunnel-client-v2

# Install
chmod +x install.sh
./install.sh

# Start
python3 app.py
```

### 4. Connect Client

1. Open: `http://localhost:3000`
2. Enter:
   - Server URL: `http://your-server-ip:7000`
   - Token: (from admin dashboard)
3. Add tunnels and click "Start"

## 📚 Complete Workflow

### As Admin

1. **Create Users**
   ```
   Admin Dashboard → Users → Create User
   - Email: user@example.com
   - Password: (set password)
   - Max Tunnels: 10
   ```

2. **Get Token**
   ```
   Click "Token" button → Copy token → Send to user
   ```

3. **Monitor Activity**
   ```
   Overview → See active users, tunnels, recent activity
   Activity → View detailed logs
   ```

4. **Manage Users**
   ```
   - Enable/Disable users
   - Change tunnel limits
   - Regenerate tokens
   - Delete users
   ```

### As User

1. **Configure Client**
   ```
   Enter server URL and token → Connect
   ```

2. **Add Tunnels**
   ```
   Name: api
   Type: HTTP
   Local Port: 8080
   Subdomain: api
   ```

3. **Start Service**
   ```
   Click "Start" → Tunnels go live
   ```

4. **Access Your Services**
   ```
   api.yourdomain.com → localhost:8080
   ```

## 🎛️ Admin Dashboard Features

### Overview Tab
- Total users count
- Active users
- Total tunnels
- Active tunnels now
- Recent activity feed

### Users Tab
- List all users
- Create new users
- View user tokens
- Enable/disable accounts
- Set tunnel limits per user
- Delete users
- Regenerate tokens

### Tunnels Tab
- See all active tunnels
- Which user owns each tunnel
- Connection status
- Last connected time

### Activity Tab
- Complete audit log
- User actions
- Login history
- Tunnel creation/deletion
- IP addresses

## 🖥️ Client Dashboard Features

### Configuration
- Connect to server with token
- Save credentials
- Disconnect

### Tunnel Management
- Add tunnels (HTTP/HTTPS/TCP)
- Enable/disable tunnels
- Delete tunnels
- Configure subdomains
- Set custom ports

### Status Monitoring
- Connection status
- Service PID
- Start/Stop/Restart controls
- Real-time updates

## 📋 Example Use Cases

### 1. Team Development Environment

**Admin:**
```bash
# Create users for team
User: developer1@team.com → Token: abc123...
User: developer2@team.com → Token: xyz789...
```

**Developers:**
```bash
# Each developer runs their services locally
Developer 1: api.yourdomain.com → localhost:8080
Developer 2: app.yourdomain.com → localhost:3000
```

### 2. Client Demos

```bash
# Quickly expose local project
Tunnel: demo
Type: HTTP
Port: 3000
Subdomain: client-demo

# Share: https://client-demo.yourdomain.com
```

### 3. Webhook Development

```bash
# GitHub webhooks
Tunnel: github-hooks
Type: HTTP
Port: 8080
Subdomain: webhooks

# Configure in GitHub: https://webhooks.yourdomain.com/payload
```

### 4. Database Access

```bash
# Temporary DB access for team
Tunnel: postgres-dev
Type: TCP
Local Port: 5432
Remote Port: 5432

# Team connects: psql -h your-server-ip -p 5432
```

## 🔐 Security Features

### Server Security
- ✅ JWT authentication for admin panel
- ✅ Bcrypt password hashing
- ✅ Token-based tunnel authentication
- ✅ Activity logging with IP tracking
- ✅ User account enable/disable
- ✅ UFW firewall configured
- ✅ Rate limiting ready
- ✅ Per-user tunnel quotas

### Client Security
- ✅ Token authentication
- ✅ Local configuration storage
- ✅ No password transmission
- ✅ Secure WebSocket connections

## 📊 Monitoring & Logs

### Server Logs
```bash
# Admin dashboard
journalctl -u tunnel-admin -f

# frp server
journalctl -u frps -f

# Access logs
tail -f /var/log/frps.log
```

### Client Logs
```bash
# Client service
journalctl -u tunnel-client -f

# Manual run
python3 app.py  # See logs in terminal
```

## 🛠️ Management Commands

### Server
```bash
# Service management (production)
systemctl status tunnel-admin
systemctl status frps
systemctl restart tunnel-admin
systemctl restart frps

# View database (production)
sqlite3 /var/lib/tunnel-server/tunnel.db

# View database (local dev)
sqlite3 ./tunnel.db
```

### Client
```bash
# Service management
systemctl status tunnel-client
systemctl restart tunnel-client

# View database
sqlite3 tunnel_client.db
```

## 🌐 DNS Configuration

Point your domain to your server:

```
Type    Name    Value
A       @       YOUR_SERVER_IP
A       *       YOUR_SERVER_IP
```

This enables:
- `yourdomain.com` → main domain
- `*.yourdomain.com` → all subdomains

## 🔧 Advanced Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret for JWT tokens | Auto-generated |
| `DB_PATH` | SQLite database path | `./tunnel.db` |
| `FRPS_CONFIG` | frp server config path | `/etc/frp/frps.ini` |

For production, set `DB_PATH=/var/lib/tunnel-server/tunnel.db` or use `install.sh`.

### Custom Tunnel Limits

```bash
# In admin dashboard
User Settings → Max Tunnels: 50
```

### Custom Ports

Edit `/etc/frp/frps.ini`:
```ini
vhost_http_port = 8080
vhost_https_port = 8443
```

### Enable HTTPS

See server README for Caddy + Let's Encrypt setup

## 📁 Project Structure

```
tunnel-server/
├── main.py                   # Entry point
├── requirements.txt          # Python dependencies
├── app/                      # Application package
│   ├── __init__.py           # App factory (create_app)
│   ├── config.py             # Settings (env vars, constants)
│   ├── database.py           # SQLite connection, init_db()
│   ├── dependencies.py       # FastAPI deps (verify_token, verify_admin)
│   ├── models/
│   │   └── schemas.py        # Pydantic models
│   ├── routes/
│   │   ├── auth.py           # POST /api/auth/login
│   │   ├── users.py          # /api/users CRUD
│   │   ├── tunnels.py        # /api/tunnels CRUD
│   │   └── stats.py          # /api/stats, /api/activity
│   ├── services/
│   │   ├── auth.py           # JWT, password hashing
│   │   ├── tunnel.py         # frpc config, URL generation
│   │   └── activity.py       # Activity logging
│   └── templates/
│       └── dashboard.html    # Admin dashboard HTML
├── tests/                    # Test suite
│   ├── conftest.py           # Pytest fixtures
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_tunnels.py
│   └── test_services/
├── scripts/
│   ├── deploy.sh             # Deploy to server via SCP
│   ├── install.sh            # Ubuntu/Debian installer
│   └── install-alpine.sh     # Alpine Linux installer
├── docs/                     # Documentation
└── README.md                 # This file
```

## 🆘 Troubleshooting

### Can't access admin dashboard
```bash
# Check if service is running
systemctl status tunnel-admin

# Check port
netstat -tuln | grep 8000

# View logs
journalctl -u tunnel-admin -n 50
```

### Client won't connect
```bash
# Verify token
# Check server URL format: http://server:7000

# Test connection
telnet your-server-ip 7000
```

### Tunnel not working
```bash
# Server side - check if tunnel is active (production path)
sqlite3 /var/lib/tunnel-server/tunnel.db "SELECT * FROM tunnels WHERE is_active = 1;"

# Server side - check if tunnel is active (local dev)
sqlite3 ./tunnel.db "SELECT * FROM tunnels WHERE is_active = 1;"

# Client side - check service
systemctl status tunnel-client
```

## 🔄 Updates

### Update Server (via deploy script)
```bash
# From your local machine
export TUNNEL_SERVER_IP=your-server-ip
./scripts/deploy.sh
# Automatically uploads files and restarts service
```

### Update Server (manual)
```bash
# Ubuntu/Debian
sudo systemctl restart tunnel-admin
sudo systemctl restart frps

# Alpine Linux
rc-service tunnel-admin restart
rc-service frps restart
```

## 🎯 Roadmap

- [ ] HTTPS with automatic Let's Encrypt
- [ ] Real-time WebSocket updates
- [ ] Traffic statistics and graphs
- [ ] Email notifications
- [ ] Custom branding
- [ ] API for programmatic access
- [ ] Docker deployment option
- [ ] Load balancing support
- [ ] Geo-distributed servers

## 📄 License

MIT License - Use freely for personal or commercial projects.

## 🤝 Support

- 📖 Documentation: See individual READMEs
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions

## 🌟 Why This Over ngrok?

1. **Cost**: $4/month vs $20/month for Pro
2. **Control**: Full access to your infrastructure
3. **Privacy**: Your data never touches third parties
4. **Unlimited**: No session timeouts or data caps
5. **Customizable**: Modify everything to your needs
6. **Learning**: Great way to understand tunneling technology
7. **Multi-user**: Built-in user management for teams

---

**Ready to deploy? Use the deploy script!**

```bash
export TUNNEL_SERVER_IP=your-server-ip
./scripts/deploy.sh
```
