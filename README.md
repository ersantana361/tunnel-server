# Tunnel Server

A self-hosted tunnel server (ngrok alternative) with admin dashboard, user management, and monitoring.

This is the **server component only**. It provides:
- Admin dashboard for managing users and tunnels
- JWT authentication and bcrypt password hashing
- SQLite database for users, tunnels, and activity logs
- Integration with [frp](https://github.com/fatedier/frp) for tunnel connections

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR SERVER                               │
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
│              │                            ▲                  │
│         [SQLite DB]                       │                  │
│    - Users & Tokens                       │ Tunnel           │
│    - Activity Logs                        │ Connection       │
│    - Statistics                           │                  │
└───────────────────────────────────────────┼──────────────────┘
                                            │
┌───────────────────────────────────────────┼──────────────────┐
│                      CLIENT MACHINE       │                  │
│                                           │                  │
│  ┌─────────────────────────────────────┐  │                  │
│  │   frp Client (frpc)                 │──┘                  │
│  │                                     │                     │
│  │   Forwards local ports to server    │                     │
│  └─────────────────────────────────────┘                     │
│              │                                               │
│              ▼                                               │
│  ┌─────────────────────────────────────┐                     │
│  │   Your Local Services               │                     │
│  │   (localhost:5000, :3000, etc.)     │                     │
│  └─────────────────────────────────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 main.py

# Or with auto-reload
uvicorn main:app --reload

# Run tests
pytest
```

- Opens at http://localhost:8000
- Creates `./tunnel.db` in current directory
- Admin credentials printed to console on first run

### Production Deployment

```bash
# Set up SSH key (one-time)
ssh-copy-id root@your-server-ip

# Deploy
export TUNNEL_SERVER_IP=your-server-ip
./scripts/deploy.sh

# First time: run installer on server
ssh root@your-server-ip
cd /opt/tunnel-server

# Ubuntu/Debian
sudo ./scripts/install.sh

# Alpine Linux
sudo ./scripts/install-alpine.sh
```

**Save the admin credentials shown!**

## Connecting Tunnels

After the server is running, you need the **frp client (frpc)** on your local machine to create tunnels.

### 1. Create a User

1. Open admin dashboard: `http://your-server:8000`
2. Login with admin credentials
3. Go to Users tab and create a user
4. Copy the user's tunnel token

### 2. Install frpc

```bash
# Download frp from https://github.com/fatedier/frp/releases
# Extract and use the frpc binary
```

### 3. Create frpc.ini

```ini
[common]
server_addr = your-server-domain.com
server_port = 7000
token = YOUR_USER_TOKEN

[my-tunnel]
type = http
local_ip = 127.0.0.1
local_port = 5000
subdomain = myapp
```

### 4. Connect

```bash
frpc -c frpc.ini
```

Your local port 5000 is now accessible at `http://myapp.your-server-domain.com`

## DNS Configuration

For subdomain-based tunnels, configure wildcard DNS:

```
Type    Name    Value
A       @       YOUR_SERVER_IP
A       *       YOUR_SERVER_IP
```

This enables:
- `yourdomain.com` - main domain
- `*.yourdomain.com` - all subdomain tunnels

Also configure `subdomain_host` in `/etc/frp/frps.ini`:

```ini
subdomain_host = yourdomain.com
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | JWT login |
| `/api/users` | GET/POST | User management (admin) |
| `/api/users/{id}` | GET/PUT/DELETE | User CRUD (admin) |
| `/api/tunnels` | GET/POST | Tunnel CRUD |
| `/api/tunnels/{id}` | DELETE | Delete tunnel |
| `/api/tunnels/{id}/config` | GET | Get frpc config |
| `/api/stats` | GET | Dashboard statistics |
| `/api/activity` | GET | Activity logs |

## Project Structure

```
tunnel-server/
├── main.py                   # Entry point
├── requirements.txt          # Python dependencies
├── app/                      # Application package
│   ├── __init__.py           # App factory (create_app)
│   ├── config.py             # Settings
│   ├── database.py           # SQLite initialization
│   ├── dependencies.py       # FastAPI dependencies
│   ├── models/
│   │   └── schemas.py        # Pydantic models
│   ├── routes/
│   │   ├── auth.py           # Authentication
│   │   ├── users.py          # User management
│   │   ├── tunnels.py        # Tunnel management
│   │   └── stats.py          # Statistics
│   ├── services/
│   │   ├── auth.py           # JWT, password hashing
│   │   ├── tunnel.py         # Config generation
│   │   └── activity.py       # Activity logging
│   └── templates/
│       └── dashboard.html    # Admin dashboard
├── tests/                    # Test suite
├── scripts/
│   ├── deploy.sh             # Deploy via SCP
│   ├── install.sh            # Ubuntu/Debian installer
│   └── install-alpine.sh     # Alpine installer
└── docs/                     # Documentation
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret for JWT tokens | Auto-generated |
| `DB_PATH` | SQLite database path | `./tunnel.db` |
| `FRPS_CONFIG` | frp server config path | `/etc/frp/frps.ini` |
| `SERVER_DOMAIN` | Domain for public URLs | Read from frps.ini |

## Troubleshooting

### Admin dashboard not accessible
```bash
# Check service status
systemctl status tunnel-admin  # Ubuntu/Debian
rc-service tunnel-admin status  # Alpine

# Check logs
journalctl -u tunnel-admin -f
```

### Tunnel shows "page not found" from frp
- Ensure frpc is running on your client machine
- Verify the token matches your user's token
- Check that your local service is running on the specified port

### Subdomain shows IP instead of domain
Set `SERVER_DOMAIN` environment variable or configure `subdomain_host` in `/etc/frp/frps.ini`:
```bash
sed -i 's/subdomain_host.*/subdomain_host = yourdomain.com/' /etc/frp/frps.ini
rc-service frps restart
```

## Documentation

- [Getting Started](docs/getting-started/README.md)
- [Architecture](docs/architecture/README.md)
- [API Reference](docs/api/README.md)
- [Configuration](docs/configuration/README.md)
- [Deployment](docs/deployment/README.md)
- [Security](docs/security/README.md)
- [DNS & Subdomains](docs/dns-subdomain-guide/README.md)
- [Troubleshooting](docs/troubleshooting/README.md)

## License

MIT License
