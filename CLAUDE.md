# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **server component** of a self-hosted tunnel service (ngrok alternative). It provides:
- Admin dashboard (FastAPI + HTML/JS) for managing users and monitoring
- Integration with frp (fast reverse proxy) server for tunnel connections
- SQLite database for users, tunnels, and activity logs

This is only the server component - there's a separate `tunnel-client-v2` project for the client side.

## Project Structure

```
tunnel-server/
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
├── app/                       # Application package
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
├── tests/                     # Test suite
│   ├── conftest.py           # Pytest fixtures
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_tunnels.py
│   └── test_services/
├── scripts/
│   ├── deploy.sh             # Deploy to server via SCP
│   ├── install.sh            # Ubuntu/Debian installer
│   └── install-alpine.sh     # Alpine Linux installer
└── docs/                      # Documentation
```

## Running the Server

```bash
# Development (requires Python 3)
pip install -r requirements.txt
python3 main.py
# Runs on http://localhost:8000
# Creates ./tunnel.db in current directory
# Admin credentials printed to console on first run

# Or with uvicorn for auto-reload
uvicorn main:app --reload

# Run tests
pytest

# Set up SSH key for password-free deploys (one-time)
ssh-copy-id root@your-server-ip

# Deploy to production server
export TUNNEL_SERVER_IP=your-server-ip
./scripts/deploy.sh

# Production installation (on server)
# Ubuntu/Debian
sudo ./scripts/install.sh

# Alpine Linux
sudo ./scripts/install-alpine.sh
```

## Architecture

**FastAPI application** with modular structure:
- `app/__init__.py` - App factory pattern with `create_app()`
- `app/config.py` - Centralized configuration
- `app/database.py` - SQLite initialization and connection
- `app/routes/` - API endpoints organized by domain
- `app/services/` - Business logic separated from routes
- `app/templates/` - HTML dashboard template

**Database Tables:**
- `users` - User accounts with tunnel tokens, quotas
- `tunnels` - Tunnel configurations per user
- `activity_logs` - Audit trail
- `server_stats` - Connection statistics

**Key Endpoints:**
- `POST /api/auth/login` - JWT login
- `GET/POST /api/users` - User management (admin only)
- `GET/POST /api/tunnels` - Tunnel CRUD
- `DELETE /api/tunnels/{id}` - Delete tunnel
- `PUT /api/tunnels/{id}/status` - Update tunnel status
- `GET /api/tunnels/{id}/config` - Get frpc configuration
- `GET /api/stats` - Dashboard statistics
- `GET /api/activity` - Activity logs

**frp Integration:**
- The install script sets up frps (frp server) on port 7000
- frps config at `/etc/frp/frps.ini`
- HTTP tunnels on port 80, HTTPS on 443
- Clients authenticate using tokens from the admin dashboard

## Configuration

Environment variables:
- `JWT_SECRET` - Secret for JWT tokens (auto-generated if not set)
- `DB_PATH` - SQLite database path (defaults to `./tunnel.db`)
- `FRPS_CONFIG` - frp server config path (defaults to `/etc/frp/frps.ini`)
- `SERVER_DOMAIN` - Domain for public URLs (read from frps.ini if not set)

Default admin credentials are printed to console on first run.

For production, set `DB_PATH=/var/lib/tunnel-server/tunnel.db` or use `install.sh` which configures this automatically.
