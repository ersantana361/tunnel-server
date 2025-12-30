# Security Documentation

Comprehensive guide to security features, best practices, and hardening for the Tunnel Server.

## Table of Contents

- [Security Overview](#security-overview)
- [Secrets Management with 1Password](#secrets-management-with-1password)
- [Authentication](#authentication)
- [Authorization](#authorization)
- [Password Security](#password-security)
- [Token Security](#token-security)
- [API Security](#api-security)
- [Infrastructure Security](#infrastructure-security)
- [Security Best Practices](#security-best-practices)
- [Security Checklist](#security-checklist)

---

## Security Overview

The Tunnel Server implements multiple layers of security:

```
┌─────────────────────────────────────────────────────────────┐
│                     Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: Network Security                                  │
│  ├── Firewall (UFW/iptables)                               │
│  ├── SSL/TLS encryption                                     │
│  └── Rate limiting (Nginx/external)                        │
│                                                              │
│  Layer 2: Authentication                                    │
│  ├── JWT tokens for dashboard access                       │
│  ├── bcrypt password hashing                               │
│  └── Tunnel tokens for frp authentication                  │
│                                                              │
│  Layer 3: Authorization                                     │
│  ├── Role-based access (admin vs user)                     │
│  ├── Resource ownership verification                       │
│  └── Per-user tunnel limits                                │
│                                                              │
│  Layer 4: Audit & Monitoring                               │
│  ├── Activity logging                                       │
│  ├── IP address tracking                                   │
│  └── Login history                                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Secrets Management with 1Password

The recommended approach for managing secrets is using 1Password CLI.

### Why 1Password?

| Feature | Auto-Generated | 1Password |
|---------|---------------|-----------|
| Credential storage | Printed to console (lost if missed) | Securely stored in vault |
| Secret rotation | Manual regeneration | Easy rotation via CLI |
| Access control | Whoever sees console | Role-based vault access |
| Audit trail | None | Full access logs |
| Multi-environment | Copy/paste | Service accounts per env |

### How It Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  setup-1password │────▶│   1Password      │────▶│   start.sh      │
│  (generates)     │     │   Vault          │     │   (injects)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  op://Tunnel/    │
                        │  tunnel-server/  │
                        │  • jwt-secret    │
                        │  • admin-password│
                        │  • admin-token   │
                        │  • frp-token     │
                        └──────────────────┘
```

### Security Benefits

1. **No secrets in code or environment files** - Only `op://` references in `.env.1password`
2. **Secrets never touch disk** - `op run` injects directly into process environment
3. **Service accounts** - Production servers use tokens with limited vault access
4. **Automatic secret rotation** - Update in 1Password, restart service

### Service Account Security

- Create dedicated service accounts per environment
- Grant minimum required vault access (read-only for most)
- Service account tokens are single-use credentials
- Tokens can be revoked instantly if compromised

---

## Authentication

### JWT (JSON Web Token) Authentication

The admin dashboard uses JWT for session management.

#### How It Works

```
1. User submits email + password
         │
         ▼
2. Server verifies credentials against bcrypt hash
         │
         ▼
3. Server generates JWT with user ID and expiration
         │
         ▼
4. Client stores JWT in localStorage
         │
         ▼
5. Client sends JWT in Authorization header for subsequent requests
         │
         ▼
6. Server validates JWT signature and expiration
```

#### JWT Structure

```
Header.Payload.Signature

Header:
{
  "typ": "JWT",
  "alg": "HS256"
}

Payload:
{
  "sub": "1",           // User ID
  "exp": 1705123456     // Expiration timestamp
}

Signature:
HMACSHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  secret_key
)
```

#### Token Configuration

```python
# In app/config.py
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

| Setting | Value | Security Impact |
|---------|-------|-----------------|
| Algorithm | HS256 | Symmetric signing (requires secret key) |
| Expiration | 30 min | Limits exposure window |
| Secret | 64-char hex | High entropy prevents brute force |

#### Token Validation

```python
def verify_token(credentials):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(user_id)
```

### Tunnel Token Authentication

Tunnel connections use a separate 64-character hex token.

#### Token Generation

```python
tunnel_token = secrets.token_hex(32)  # 64 hex characters
```

#### Token Properties

| Property | Value | Description |
|----------|-------|-------------|
| Length | 64 characters | 256 bits of entropy |
| Format | Hexadecimal | 0-9, a-f |
| Uniqueness | Per user | Each user gets unique token |
| Lifetime | Indefinite | Valid until regenerated |

#### Token Usage

The token is used by the frp client to authenticate with the server:

```ini
# Client frpc.ini
[common]
server_addr = your-server
server_port = 7000
token = 745d5d29f549f9e16cc8d88c9dede02edf177937a5ce7480d8ee3330c99f3c41
```

---

## Authorization

### Role-Based Access Control

| Role | Dashboard Access | User Management | View All Tunnels |
|------|------------------|-----------------|------------------|
| Admin | Full | Yes | Yes |
| User | Limited | No | Own only |

### Admin Verification

```python
def verify_admin(user_id: int = Depends(verify_token)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result or not result[0]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id
```

### Protected Endpoints

| Endpoint | Auth Required | Admin Required |
|----------|---------------|----------------|
| `GET /` | No | No |
| `POST /api/auth/login` | No | No |
| `GET /api/users` | Yes | Yes |
| `POST /api/users` | Yes | Yes |
| `PUT /api/users/{id}` | Yes | Yes |
| `DELETE /api/users/{id}` | Yes | Yes |
| `GET /api/tunnels` | Yes | No (filtered) |
| `GET /api/stats` | Yes | Yes |
| `GET /api/activity` | Yes | Yes |

### Resource Ownership

Non-admin users can only see their own tunnels:

```python
if is_admin:
    # Show all tunnels
    cursor.execute("SELECT t.*, u.email... FROM tunnels t JOIN users u...")
else:
    # Show only user's tunnels
    cursor.execute("SELECT * FROM tunnels WHERE user_id = ?", (user_id,))
```

---

## Password Security

### bcrypt Hashing

Passwords are hashed using bcrypt with automatic salt generation.

```python
import bcrypt

# Hashing a password
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# Verifying a password
if bcrypt.checkpw(submitted_password.encode(), stored_hash):
    # Password is correct
```

### bcrypt Properties

| Property | Value | Description |
|----------|-------|-------------|
| Algorithm | bcrypt | Designed for passwords |
| Salt | Automatic | Unique per hash |
| Work Factor | 12 (default) | Computational cost |
| Output | 60 characters | Includes algorithm ID and salt |

### Password Hash Format

```
$2b$12$saltcharacters....hashedpasswordcharacters

$2b$ = bcrypt algorithm identifier
$12$ = work factor (2^12 iterations)
salt = 22 base64 characters
hash = 31 base64 characters
```

### Password Verification Flow

```
1. User submits password
         │
         ▼
2. Retrieve stored hash from database
         │
         ▼
3. bcrypt.checkpw(submitted, stored)
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  Match    No Match
    │         │
    ▼         ▼
 Login     Reject
 Success   (401)
```

---

## Token Security

### JWT Secret Key

#### Generation

```python
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
```

#### Best Practices

1. **Never commit to version control**
2. **Use environment variables**
3. **Use at least 32 bytes (64 hex chars)**
4. **Rotate periodically**

#### Production Configuration

```bash
# Generate a secure secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# Set in environment
export JWT_SECRET="your-generated-secret-here"

# Or in systemd service
Environment="JWT_SECRET=your-generated-secret-here"
```

### Tunnel Token Security

#### Regeneration

Tokens can be regenerated if compromised:

```python
@app.post("/api/users/{user_id}/regenerate-token")
async def regenerate_token(user_id: int, admin_id: int = Depends(verify_admin)):
    new_token = secrets.token_hex(32)
    # Update in database
    cursor.execute("UPDATE users SET token = ? WHERE id = ?", (new_token, user_id))
```

#### Token Compromise Response

1. Identify affected user
2. Regenerate token via admin dashboard
3. Notify user to update client configuration
4. Review activity logs for suspicious activity

---

## API Security

### Input Validation

Pydantic models validate all input:

```python
class UserCreate(BaseModel):
    email: EmailStr          # Validates email format
    password: str            # Required
    max_tunnels: int = 10    # Default value

class UserLogin(BaseModel):
    email: str
    password: str
```

### SQL Injection Prevention

Parameterized queries prevent SQL injection:

```python
# SAFE - Parameterized query
cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))

# UNSAFE - String concatenation (NOT used)
cursor.execute(f"SELECT * FROM users WHERE email = '{user.email}'")  # DON'T DO THIS
```

### CORS (Cross-Origin Resource Sharing)

Currently, no CORS headers are configured (single-origin by default).

For production with separate frontend:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://admin.yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Infrastructure Security

### Firewall Configuration

```bash
# UFW (Uncomplicated Firewall)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8000/tcp  # Admin dashboard
sudo ufw allow 7000/tcp  # frp control
sudo ufw allow 80/tcp    # HTTP tunnels
sudo ufw allow 443/tcp   # HTTPS tunnels
sudo ufw enable
```

### SSL/TLS Configuration

#### Let's Encrypt with Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d admin.yourdomain.com
```

#### Nginx SSL Settings

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### Rate Limiting

#### Nginx Rate Limiting

```nginx
# In http block
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

# In server block
location /api/auth/login {
    limit_req zone=login burst=5 nodelay;
    proxy_pass http://127.0.0.1:8000;
}
```

#### Fail2ban for Login Attempts

```ini
# /etc/fail2ban/filter.d/tunnel-admin.conf
[Definition]
failregex = ^.*POST /api/auth/login.*401.*$
ignoreregex =

# /etc/fail2ban/jail.local
[tunnel-admin]
enabled = true
port = http,https
filter = tunnel-admin
logpath = /var/log/nginx/access.log
maxretry = 5
bantime = 3600
```

---

## Security Best Practices

### 1. Environment Variables

```bash
# Never hardcode secrets
JWT_SECRET=your-secret  # In environment, not code

# Use .env files for development (add to .gitignore)
echo ".env" >> .gitignore
```

### 2. Database Security

```bash
# Restrict database file permissions
chmod 600 /var/lib/tunnel-server/tunnel.db
chown tunnel-user:tunnel-group /var/lib/tunnel-server/tunnel.db
```

### 3. Principle of Least Privilege

```bash
# Create dedicated service user
sudo useradd -r -s /bin/false tunnel-admin

# Run service as non-root
# In systemd: User=tunnel-admin
```

### 4. Regular Updates

```bash
# Keep system updated
sudo apt update && sudo apt upgrade -y

# Update Python dependencies
pip install --upgrade -r requirements.txt
```

### 5. Logging and Monitoring

```bash
# Enable and review logs
journalctl -u tunnel-admin -f

# Set up log rotation
# /etc/logrotate.d/tunnel-admin
```

### 6. Backup Encryption

```bash
# Encrypt backups
gpg -c tunnel_backup.db
# Creates tunnel_backup.db.gpg
```

---

## Security Checklist

### Development

- [ ] Use auto-generated JWT_SECRET (default)
- [ ] Database in local directory
- [ ] No sensitive data in version control
- [ ] Review code for SQL injection

### Pre-Production

- [ ] Generate production JWT_SECRET
- [ ] Set up dedicated database directory
- [ ] Configure firewall rules
- [ ] Plan SSL/TLS implementation

### Production

- [ ] Strong JWT_SECRET set via environment
- [ ] SSL/TLS enabled (Let's Encrypt)
- [ ] Firewall configured and enabled
- [ ] Rate limiting configured
- [ ] Fail2ban configured
- [ ] Non-root service user
- [ ] Database file permissions restricted
- [ ] Automated backups enabled
- [ ] Log monitoring configured
- [ ] Regular update schedule

### Ongoing

- [ ] Regular password rotation for admin
- [ ] Token regeneration when team changes
- [ ] Security updates applied promptly
- [ ] Periodic security audits
- [ ] Review activity logs weekly
- [ ] Test backup restoration quarterly

---

## Incident Response

### Suspected Compromise

1. **Isolate**: Disable affected user accounts
2. **Investigate**: Review activity logs
3. **Contain**: Regenerate all tokens
4. **Eradicate**: Remove unauthorized access
5. **Recover**: Restore from clean backup if needed
6. **Lessons**: Update security measures

### Log Analysis

```bash
# Find failed login attempts
grep "401" /var/log/nginx/access.log | grep "login"

# Find suspicious activity
sqlite3 tunnel.db "SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 100;"

# Check for unusual patterns
sqlite3 tunnel.db "SELECT ip_address, COUNT(*) as count FROM activity_logs GROUP BY ip_address ORDER BY count DESC;"
```

---

## Related Documentation

- [Architecture](../architecture/README.md) - System design
- [API Reference](../api/README.md) - Endpoint security
- [Configuration](../configuration/README.md) - Security settings
- [Deployment](../deployment/README.md) - Production security
