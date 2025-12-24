# Troubleshooting Guide

Comprehensive guide for diagnosing and resolving common issues with the Tunnel Server.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Startup Issues](#startup-issues)
- [Authentication Issues](#authentication-issues)
- [Connection Issues](#connection-issues)
- [Database Issues](#database-issues)
- [Performance Issues](#performance-issues)
- [Common Error Messages](#common-error-messages)
- [Log Analysis](#log-analysis)
- [Getting Help](#getting-help)

---

## Quick Diagnostics

Run these commands to quickly assess system status:

```bash
# Check if services are running
systemctl status tunnel-admin
systemctl status frps

# Check listening ports
netstat -tuln | grep -E '7000|8000|80|443'

# Check disk space
df -h

# Check memory
free -h

# Test admin dashboard
curl -I http://localhost:8000

# View recent logs
journalctl -u tunnel-admin -n 50 --no-pager
```

---

## Installation Issues

### Python Version Too Old

**Symptom:**
```
SyntaxError: invalid syntax
# or
ModuleNotFoundError: No module named 'typing_extensions'
```

**Solution:**
```bash
# Check Python version
python3 --version

# Install Python 3.10+ on Ubuntu
sudo apt update
sudo apt install python3.10 python3.10-pip

# Use specific version
python3.10 main.py
```

### Pip Installation Fails

**Symptom:**
```
error: externally-managed-environment
```

**Solution:**
```bash
# Option 1: Use --break-system-packages
pip install -r requirements.txt --break-system-packages

# Option 2: Use virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Permission Denied for /var/lib

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/var/lib/tunnel-server'
```

**Solution:**
```bash
# Create directory with proper permissions
sudo mkdir -p /var/lib/tunnel-server
sudo chown $USER:$USER /var/lib/tunnel-server

# Or use local database for development
DB_PATH=./tunnel.db python3 main.py
```

### frp Download Fails

**Symptom:**
```
wget: unable to resolve host address
```

**Solution:**
```bash
# Check DNS
cat /etc/resolv.conf

# Use alternative DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# Manual download
curl -L -o frp.tar.gz https://github.com/fatedier/frp/releases/download/v0.52.3/frp_0.52.3_linux_amd64.tar.gz
```

---

## Startup Issues

### Port Already in Use

**Symptom:**
```
OSError: [Errno 98] Address already in use
```

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000
# or
netstat -tuln | grep 8000

# Kill the process
kill -9 <PID>

# Or use different port
# Edit main.py: uvicorn.run(app, port=9000)
```

### Module Not Found

**Symptom:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Check if installed
pip list | grep fastapi

# Install specific package
pip install fastapi uvicorn
```

### Database Initialization Fails

**Symptom:**
```
sqlite3.OperationalError: unable to open database file
```

**Solution:**
```bash
# Check if directory exists
ls -la /var/lib/tunnel-server/

# Create directory
sudo mkdir -p /var/lib/tunnel-server
sudo chmod 755 /var/lib/tunnel-server

# Check disk space
df -h /var/lib/
```

### Service Won't Start

**Symptom:**
```bash
systemctl status tunnel-admin
# shows: Active: failed
```

**Solution:**
```bash
# View detailed error
journalctl -u tunnel-admin -n 100 --no-pager

# Check service file
cat /etc/systemd/system/tunnel-admin.service

# Test manually
cd /opt/tunnel-server
python3 main.py

# Reload after fixing
sudo systemctl daemon-reload
sudo systemctl restart tunnel-admin
```

---

## Authentication Issues

### Can't Login - Invalid Credentials

**Symptom:**
```json
{"detail": "Invalid credentials"}
```

**Causes & Solutions:**

1. **Wrong password**
   ```bash
   # Check if user exists
   sqlite3 tunnel.db "SELECT email FROM users WHERE email = 'admin@localhost';"
   ```

2. **Account disabled**
   ```bash
   # Check if active
   sqlite3 tunnel.db "SELECT email, is_active FROM users WHERE email = 'admin@localhost';"

   # Enable account
   sqlite3 tunnel.db "UPDATE users SET is_active = 1 WHERE email = 'admin@localhost';"
   ```

3. **Lost admin password**
   ```bash
   # Option 1: Reset database (loses all data)
   rm tunnel.db
   python3 main.py  # New credentials will be generated

   # Option 2: Update password manually
   python3 -c "import bcrypt; print(bcrypt.hashpw(b'newpassword', bcrypt.gensalt()).decode())"
   sqlite3 tunnel.db "UPDATE users SET password_hash = '<output>' WHERE email = 'admin@localhost';"
   ```

### JWT Token Expired

**Symptom:**
```json
{"detail": "Token expired"}
```

**Solution:**
- Login again to get a new token
- Tokens expire after 30 minutes by default

### Token Invalid After Restart

**Symptom:**
```json
{"detail": "Invalid token"}
```

**Cause:** JWT_SECRET changed between restarts

**Solution:**
```bash
# Set a fixed JWT_SECRET
export JWT_SECRET="your-consistent-secret"
python3 main.py

# Or in systemd service
Environment="JWT_SECRET=your-consistent-secret"
```

---

## Connection Issues

### Can't Access Dashboard

**Symptom:** Browser shows "Connection refused" or timeout

**Diagnostics:**
```bash
# Is server running?
ps aux | grep main.py

# Is port listening?
netstat -tuln | grep 8000

# Is firewall blocking?
sudo ufw status
```

**Solutions:**

1. **Server not running**
   ```bash
   python3 main.py
   # or
   sudo systemctl start tunnel-admin
   ```

2. **Firewall blocking**
   ```bash
   sudo ufw allow 8000/tcp
   ```

3. **Listening on wrong interface**
   ```bash
   # Check if listening on all interfaces
   netstat -tuln | grep 8000
   # Should show: 0.0.0.0:8000

   # If shows 127.0.0.1:8000, edit main.py:
   # uvicorn.run(app, host="0.0.0.0", port=8000)
   ```

### frp Client Can't Connect

**Symptom:** Client shows connection refused or timeout

**Diagnostics:**
```bash
# Server side
systemctl status frps
netstat -tuln | grep 7000

# Test from client
telnet your-server-ip 7000
nc -zv your-server-ip 7000
```

**Solutions:**

1. **frps not running**
   ```bash
   sudo systemctl start frps
   ```

2. **Port blocked**
   ```bash
   sudo ufw allow 7000/tcp
   ```

3. **Wrong token**
   ```bash
   # Verify token in client config matches user's token
   sqlite3 tunnel.db "SELECT token FROM users WHERE email = 'user@example.com';"
   ```

### Tunnel Not Accessible

**Symptom:** Tunnel shows active but can't access via subdomain

**Diagnostics:**
```bash
# Check DNS
dig subdomain.yourdomain.com

# Check frps logs
journalctl -u frps -f

# Check if port 80 is listening
netstat -tuln | grep 80
```

**Solutions:**

1. **DNS not configured**
   ```
   Add A record: *.yourdomain.com -> YOUR_SERVER_IP
   ```

2. **Port 80 blocked**
   ```bash
   sudo ufw allow 80/tcp
   ```

3. **Local service not running**
   ```bash
   # Ensure local service is running
   curl http://localhost:8080  # or whatever local port
   ```

---

## Database Issues

### Database Locked

**Symptom:**
```
sqlite3.OperationalError: database is locked
```

**Solutions:**
```bash
# Find processes using database
fuser tunnel.db

# Kill stuck processes
sudo fuser -k tunnel.db

# If persistent, restart service
sudo systemctl restart tunnel-admin
```

### Database Corrupted

**Symptom:**
```
sqlite3.DatabaseError: database disk image is malformed
```

**Solutions:**
```bash
# Check integrity
sqlite3 tunnel.db "PRAGMA integrity_check;"

# If corrupted, attempt recovery
sqlite3 tunnel.db ".recover" | sqlite3 tunnel_recovered.db

# Or restore from backup
cp /var/backups/tunnel-server/tunnel_latest.db tunnel.db
```

### Out of Disk Space

**Symptom:**
```
sqlite3.OperationalError: database or disk is full
```

**Solutions:**
```bash
# Check disk space
df -h

# Find large files
du -sh /var/lib/tunnel-server/*

# Clean up old logs
sqlite3 tunnel.db "DELETE FROM activity_logs WHERE created_at < datetime('now', '-30 days');"
sqlite3 tunnel.db "VACUUM;"
```

---

## Performance Issues

### Slow Response Times

**Diagnostics:**
```bash
# Check CPU usage
top

# Check memory
free -h

# Check database size
ls -lh tunnel.db
```

**Solutions:**

1. **Add database indexes**
   ```sql
   sqlite3 tunnel.db
   CREATE INDEX idx_users_email ON users(email);
   CREATE INDEX idx_activity_created ON activity_logs(created_at);
   ANALYZE;
   ```

2. **Clean up old data**
   ```sql
   DELETE FROM activity_logs WHERE created_at < datetime('now', '-90 days');
   VACUUM;
   ```

3. **Increase workers**
   ```python
   # In main.py
   uvicorn.run(app, workers=4)
   ```

### High Memory Usage

**Diagnostics:**
```bash
# Check memory per process
ps aux --sort=-%mem | head
```

**Solutions:**
```bash
# Restart service to clear memory
sudo systemctl restart tunnel-admin

# Add memory limit in systemd
# MemoryLimit=256M
```

---

## Common Error Messages

### Error Reference Table

| Error | Cause | Solution |
|-------|-------|----------|
| `Address already in use` | Port 8000 occupied | Kill existing process or change port |
| `Permission denied` | Insufficient permissions | Run with sudo or fix file permissions |
| `Module not found` | Missing dependency | `pip install -r requirements.txt` |
| `Invalid credentials` | Wrong email/password | Check credentials or reset password |
| `Token expired` | JWT expired | Login again |
| `Admin access required` | Non-admin accessing admin endpoint | Use admin account |
| `Email already exists` | Duplicate email | Use different email |
| `Database locked` | Concurrent access issue | Restart service |
| `Connection refused` | Service not running | Start the service |

---

## Log Analysis

### Viewing Logs

```bash
# Real-time admin logs
journalctl -u tunnel-admin -f

# Last 100 lines
journalctl -u tunnel-admin -n 100

# Logs from specific time
journalctl -u tunnel-admin --since "2024-01-15 10:00:00"

# Logs with errors only
journalctl -u tunnel-admin -p err
```

### Log Patterns

**Successful login:**
```
INFO: 192.168.1.100:54321 - "POST /api/auth/login HTTP/1.1" 200 OK
```

**Failed login:**
```
INFO: 192.168.1.100:54321 - "POST /api/auth/login HTTP/1.1" 401 Unauthorized
```

**Server error:**
```
ERROR: Exception in ASGI application
Traceback...
```

### Searching Logs

```bash
# Find all errors
journalctl -u tunnel-admin | grep -i error

# Find login attempts
journalctl -u tunnel-admin | grep "login"

# Find specific IP
journalctl -u tunnel-admin | grep "192.168.1.100"
```

---

## Getting Help

### Before Asking for Help

Collect this information:

```bash
# System info
uname -a
python3 --version
pip list | grep -E "fastapi|uvicorn|pydantic"

# Service status
systemctl status tunnel-admin
systemctl status frps

# Recent logs
journalctl -u tunnel-admin -n 50 --no-pager

# Configuration
cat /etc/systemd/system/tunnel-admin.service
```

### Reporting Issues

Include:
1. Steps to reproduce
2. Expected behavior
3. Actual behavior
4. System information (from above)
5. Relevant log excerpts

### Resources

- **Documentation**: This docs folder
- **GitHub Issues**: Report bugs
- **GitHub Discussions**: Ask questions

---

## Quick Fixes Cheatsheet

```bash
# Restart everything
sudo systemctl restart tunnel-admin frps

# Reset database (CAUTION: loses data)
rm tunnel.db && python3 main.py

# Fix permissions
sudo chown -R $USER:$USER /var/lib/tunnel-server

# Clear firewall issues
sudo ufw allow 7000/tcp && sudo ufw allow 8000/tcp

# Check what's listening
sudo netstat -tulpn

# View real-time logs
journalctl -u tunnel-admin -f

# Test API
curl http://localhost:8000/api/stats -H "Authorization: Bearer <token>"
```

---

## Related Documentation

- [Getting Started](../getting-started/README.md) - Initial setup
- [Configuration](../configuration/README.md) - Configuration options
- [Deployment](../deployment/README.md) - Production issues
- [Security](../security/README.md) - Security-related issues
