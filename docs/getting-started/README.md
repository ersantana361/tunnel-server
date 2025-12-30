# Getting Started

This guide walks you through setting up the Tunnel Server, from local development to production deployment, and connecting your first tunnel.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [First Run](#first-run)
- [Understanding Admin Credentials](#understanding-admin-credentials)
- [Creating Your First User](#creating-your-first-user)
- [Connecting Your First Tunnel](#connecting-your-first-tunnel)
- [Next Steps](#next-steps)

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.8+ | 3.10+ |
| RAM | 512 MB | 1 GB |
| Disk Space | 100 MB | 500 MB |
| OS | Linux/macOS/Windows | Ubuntu 22.04+ |

### Required Software

1. **Python 3.8 or higher**
   ```bash
   # Check your Python version
   python3 --version
   ```

2. **pip (Python package manager)**
   ```bash
   # Check pip is installed
   pip --version
   # or
   python3 -m pip --version
   ```

3. **SQLite3** (usually pre-installed)
   ```bash
   # Check SQLite version
   sqlite3 --version
   ```

4. **1Password CLI** (recommended for secrets management)
   ```bash
   # macOS
   brew install 1password-cli

   # Linux - see https://developer.1password.com/docs/cli/get-started

   # Verify installation
   op --version
   ```

---

## Local Development Setup

### Step 1: Clone or Download the Project

```bash
# If using git
git clone <repository-url>
cd tunnel-server

# Or navigate to your project directory
cd /path/to/tunnel-server
```

### Step 2: Install Python Dependencies

```bash
# Install all required packages
pip install -r requirements.txt
```

**What gets installed:**

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.109.0 | Web framework for the API and dashboard |
| uvicorn | 0.27.0 | ASGI server to run the application |
| pydantic | 2.5.3 | Data validation and serialization |
| python-jose | 3.3.0 | JWT token creation and verification |
| bcrypt | 4.1.2 | Secure password hashing |
| passlib | 1.7.4 | Password hashing utilities |
| python-multipart | 0.0.6 | Form data parsing |

### Step 3: Verify Installation

```bash
# Check that all packages are installed
pip list | grep -E "fastapi|uvicorn|pydantic|python-jose|bcrypt"
```

---

## First Run

### Starting the Server

```bash
python3 main.py

# Or with auto-reload for development
uvicorn main:app --reload
```

**Expected Output:**

```
============================================================
ADMIN CREDENTIALS - SAVE THESE!
============================================================
Email: admin@localhost
Password: <random-generated-password>
Token: <64-character-hex-token>
============================================================

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### What Happens on First Run

1. **Database Creation**: A SQLite database file (`tunnel.db`) is created in the current directory
2. **Table Initialization**: Four tables are created automatically:
   - `users` - User accounts and authentication
   - `tunnels` - Tunnel configurations
   - `activity_logs` - Audit trail
   - `server_stats` - Usage statistics
3. **Admin Account**: A default admin account is generated with:
   - Email: `admin@localhost`
   - Random secure password
   - Random tunnel token
4. **Server Start**: The FastAPI server starts on port 8000

### Accessing the Dashboard

Open your web browser and navigate to:

```
http://localhost:8000
```

You'll see the login page for the admin dashboard.

---

## Understanding Admin Credentials

### Recommended: Use 1Password

The best way to manage credentials is with 1Password CLI:

```bash
# Generate secrets and save to 1Password (one-time)
./scripts/setup-1password.sh

# Run with 1Password secret injection
./scripts/start.sh
# Or: op run --env-file=.env.1password -- python3 main.py
```

This stores credentials securely in your 1Password vault (`Tunnel` → `tunnel-server`).

### Alternative: Auto-Generated Credentials

If not using 1Password, credentials are randomly generated on first run:

1. **No default passwords**: Every installation has unique credentials
2. **Secure tokens**: 64-character hex tokens are cryptographically secure
3. **Password strength**: Auto-generated passwords use URL-safe characters

### Credential Components

| Credential | Format | Purpose |
|------------|--------|---------|
| Email | `admin@localhost` | Login identifier |
| Password | 22-char URL-safe | Dashboard authentication |
| Token | 64-char hex | API/tunnel authentication |

### Saving Your Credentials

**With 1Password (recommended)**: Credentials are automatically saved to your vault.

**Without 1Password**: The credentials are only shown once at first run. Save them immediately!

```bash
# Option 1: Redirect output to a file
python3 main.py 2>&1 | tee first_run.log

# Option 2: Copy from terminal immediately

# Option 3: Query the database (not recommended for password)
sqlite3 tunnel.db "SELECT email, token FROM users WHERE is_admin = 1;"
```

### Resetting Admin Password

If you lose your admin password, you'll need to either:

1. Delete the database and restart (loses all data)
   ```bash
   rm tunnel.db
   python3 main.py
   ```

2. Manually update the password hash in the database (advanced)

---

## Creating Your First User

Once logged into the admin dashboard:

### Step 1: Navigate to Users Tab

Click on the "Users" tab in the dashboard navigation.

### Step 2: Click "Create User"

Fill in the user details:

| Field | Description | Example |
|-------|-------------|---------|
| Email | User's email address | `developer@example.com` |
| Password | User's login password | `secure-password-123` |
| Max Tunnels | Maximum tunnels allowed | `10` |

### Step 3: Save the Tunnel Token

After creating the user, a **tunnel token** is displayed. This token is used by the client application to authenticate tunnel connections.

**Important**: Copy and securely share this token with the user. They will need it to connect their client.

---

## Connecting Your First Tunnel

The server is only half the equation. To actually expose your local services, you need the **frp client (frpc)** running on your local machine.

### Step 1: Install frpc

Download frp from [GitHub releases](https://github.com/fatedier/frp/releases):

```bash
# Example for Linux amd64
wget https://github.com/fatedier/frp/releases/download/v0.51.3/frp_0.51.3_linux_amd64.tar.gz
tar -xzf frp_0.51.3_linux_amd64.tar.gz
cd frp_0.51.3_linux_amd64
```

### Step 2: Create Configuration

Create `frpc.ini` with your tunnel configuration:

```ini
[common]
server_addr = your-server-ip-or-domain
server_port = 7000
token = YOUR_USER_TOKEN

[my-tunnel]
type = http
local_ip = 127.0.0.1
local_port = 3000
subdomain = myapp
```

Replace:
- `server_addr` - Your server's IP or domain
- `token` - The tunnel token from your user account
- `local_port` - The port your local service runs on
- `subdomain` - The subdomain for your tunnel

### Step 3: Start a Local Service

```bash
# Example: simple HTTP server
python3 -m http.server 3000
```

### Step 4: Connect the Tunnel

```bash
./frpc -c frpc.ini
```

You should see:
```
[I] login to server success
[I] [my-tunnel] start proxy success
```

### Step 5: Access Your Service

Your local service is now accessible at:
- With domain: `http://myapp.yourdomain.com`
- With IP only: Requires proxy configuration (see DNS guide)

---

## Next Steps

Now that you have the server running:

1. **[Architecture](../architecture/README.md)** - Understand how the system works
2. **[API Documentation](../api/README.md)** - Learn about available endpoints
3. **[Configuration](../configuration/README.md)** - Customize your installation
4. **[Deployment](../deployment/README.md)** - Deploy to production
5. **[Security](../security/README.md)** - Understand security features

---

## Quick Reference

### Common Commands

```bash
# Start the server
python3 main.py

# Start with auto-reload for development
uvicorn main:app --reload

# Start with custom database path
DB_PATH=/custom/path/tunnel.db python3 main.py

# Run tests
pytest

# View the database
sqlite3 tunnel.db

# Check active users
sqlite3 tunnel.db "SELECT email, is_active FROM users;"
```

### Default Ports

| Service | Port | URL |
|---------|------|-----|
| Admin Dashboard | 8000 | http://localhost:8000 |
| frp Server (production) | 7000 | - |
| HTTP Tunnels (production) | 80 | - |
| HTTPS Tunnels (production) | 443 | - |

### File Locations (Development)

| File | Location |
|------|----------|
| Entry Point | `./main.py` |
| Application | `./app/` |
| Database | `./tunnel.db` |
| Dependencies | `./requirements.txt` |
| Tests | `./tests/` |
