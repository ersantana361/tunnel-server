# Tunnel Server Documentation

Welcome to the comprehensive documentation for the Tunnel Server - a self-hosted ngrok alternative with admin dashboard, user management, and monitoring.

## Documentation Index

| Section | Description |
|---------|-------------|
| [Getting Started](./getting-started/README.md) | Installation, first run, and basic setup |
| [Architecture](./architecture/README.md) | System design, components, and data flow |
| [API Reference](./api/README.md) | Complete REST API documentation |
| [Configuration](./configuration/README.md) | Environment variables and settings |
| [Deployment](./deployment/README.md) | Production deployment guide |
| [DNS & Subdomains](./dns-subdomain-guide/README.md) | DNS setup with Netlify, Cloudflare, etc. |
| [Database](./database/README.md) | Schema, queries, and data management |
| [Security](./security/README.md) | Authentication, authorization, and best practices |
| [Admin Dashboard](./admin-dashboard/README.md) | Using the web interface |
| [Troubleshooting](./troubleshooting/README.md) | Common issues and solutions |

---

## Quick Links

### New to Tunnel Server?

Start here:
1. [Getting Started](./getting-started/README.md) - Set up your first instance
2. [Admin Dashboard](./admin-dashboard/README.md) - Learn the web interface
3. [Configuration](./configuration/README.md) - Customize your setup

### Deploying to Production?

Essential reading:
1. [Deployment](./deployment/README.md) - Production setup guide
2. [Security](./security/README.md) - Security hardening
3. [Troubleshooting](./troubleshooting/README.md) - Common issues

### Building Integrations?

Developer resources:
1. [API Reference](./api/README.md) - REST API documentation
2. [Database](./database/README.md) - Schema reference
3. [Architecture](./architecture/README.md) - System design

---

## Quick Start

### Development (2 minutes)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 main.py

# Or with auto-reload
uvicorn main:app --reload

# Run tests
pytest

# Access at http://localhost:8000
```

### Production (10 minutes)

```bash
# From your local machine
export TUNNEL_SERVER_IP=your-server-ip
./scripts/deploy.sh

# Then SSH and run installer (first time only)
ssh root@your-server-ip
cd /opt/tunnel-server
./scripts/install-alpine.sh  # or scripts/install.sh for Ubuntu/Debian

# Access at http://your-server:8000
```

### Connecting Tunnels

After the server is running, use the frp client on your local machine:

```bash
# Create frpc.ini
cat > frpc.ini << 'EOF'
[common]
server_addr = your-server-domain.com
server_port = 7000
token = YOUR_USER_TOKEN

[my-app]
type = http
local_ip = 127.0.0.1
local_port = 3000
subdomain = myapp
EOF

# Connect
frpc -c frpc.ini
```

Access your local service at: `http://myapp.your-server-domain.com`

---

## Documentation Structure

```
docs/
├── README.md                 # This file - documentation index
│
├── getting-started/
│   └── README.md            # Installation and first run
│
├── architecture/
│   └── README.md            # System design and components
│
├── api/
│   └── README.md            # REST API reference
│
├── configuration/
│   └── README.md            # Environment variables and settings
│
├── deployment/
│   └── README.md            # Production deployment guide
│
├── dns-subdomain-guide/
│   └── README.md            # DNS setup with Netlify, Cloudflare, etc.
│
├── database/
│   └── README.md            # Schema and data management
│
├── security/
│   └── README.md            # Security features and best practices
│
├── admin-dashboard/
│   └── README.md            # Web interface guide
│
└── troubleshooting/
    └── README.md            # Common issues and solutions
```

---

## Key Concepts

### Components

| Component | Description | Port |
|-----------|-------------|------|
| Admin Dashboard | Web UI for management | 8000 |
| frp Server | Tunnel proxy server | 7000 |
| SQLite Database | Data storage | N/A |

### User Roles

| Role | Capabilities |
|------|--------------|
| Admin | Full access - manage users, view all data |
| User | Limited - own tunnels only |

### Authentication

| Type | Purpose |
|------|---------|
| JWT Token | Dashboard authentication (30 min expiry) |
| Tunnel Token | frp client authentication (no expiry) |

---

## Configuration Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | Auto-generated | JWT signing key |
| `DB_PATH` | `./tunnel.db` | Database location |
| `FRPS_CONFIG` | `/etc/frp/frps.ini` | frp config path |

### Common Commands

```bash
# Start development server
python3 main.py

# With auto-reload
uvicorn main:app --reload

# Run tests
pytest

# View service status (Ubuntu/Debian)
systemctl status tunnel-admin

# View service status (Alpine)
rc-service tunnel-admin status

# View logs (Ubuntu/Debian)
journalctl -u tunnel-admin -f

# View logs (Alpine)
tail -f /var/log/tunnel-admin.log

# Access database
sqlite3 tunnel.db
```

---

## API Quick Reference

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@localhost","password":"your-password"}'
```

### Common Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Authenticate |
| GET | `/api/users` | List users (admin) |
| POST | `/api/users` | Create user (admin) |
| GET | `/api/tunnels` | List tunnels |
| GET | `/api/stats` | Get statistics (admin) |
| GET | `/api/activity` | Get activity logs (admin) |

---

## Troubleshooting Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| Can't start server | Check port 8000: `netstat -tuln \| grep 8000` |
| Login fails | Verify credentials or reset: `rm tunnel.db` |
| Token invalid | Set consistent JWT_SECRET |
| Permission denied | Fix permissions: `chmod 755 /var/lib/tunnel-server` |

See [Troubleshooting](./troubleshooting/README.md) for detailed solutions.

---

## Contributing to Documentation

### Style Guidelines

- Use clear, concise language
- Include code examples
- Add tables for reference data
- Link to related documentation

### Updating Documentation

1. Edit the relevant README.md file
2. Update this index if adding new sections
3. Test all code examples

---

## Version

This documentation covers Tunnel Server v2.

---

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Documentation**: You're reading it!
