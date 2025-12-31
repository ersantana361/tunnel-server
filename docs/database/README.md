# Database Documentation

Complete reference for the Tunnel Server database schema, queries, and management.

## Table of Contents

- [Overview](#overview)
- [Schema](#schema)
- [Tables](#tables)
- [Relationships](#relationships)
- [Common Queries](#common-queries)
- [Data Management](#data-management)
- [Migration](#migration)

---

## Overview

The Tunnel Server uses SQLite as its database engine. SQLite was chosen for its:

- **Zero Configuration**: No separate database server required
- **File-Based**: Easy to backup and move
- **Embedded**: Included in Python's standard library
- **Sufficient Performance**: Adequate for expected workloads

### Database Location

| Environment | Path |
|-------------|------|
| Development | `./tunnel.db` |
| Production | `/var/lib/tunnel-server/tunnel.db` |
| Custom | `$DB_PATH` environment variable |

### Connecting to Database

```bash
# Development
sqlite3 ./tunnel.db

# Production
sqlite3 /var/lib/tunnel-server/tunnel.db

# Show tables
.tables

# Show schema
.schema

# Enable column headers
.headers on
.mode column
```

---

## Schema

### Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│  ┌──────────────┐          ┌───────────────┐          ┌─────────────────┐   │
│  │    users     │          │    tunnels    │          │ tunnel_metrics  │   │
│  ├──────────────┤          ├───────────────┤          ├─────────────────┤   │
│  │ id (PK)      │◄────────┤│ user_id (FK)  │◄────────┤│ tunnel_id (FK)  │   │
│  │ email        │     1:N  │ id (PK)       │     1:N  │ id (PK)         │   │
│  │ password_hash│          │ name          │          │ tunnel_name     │   │
│  │ token        │          │ type          │          │ traffic_in      │   │
│  │ is_admin     │          │ subdomain     │          │ traffic_out     │   │
│  │ is_active    │          │ remote_port   │          │ current_conns   │   │
│  │ max_tunnels  │          │ is_active     │          │ status          │   │
│  │ created_at   │          │ created_at    │          │ collected_at    │   │
│  │ last_login   │          │ last_connected│          └─────────────────┘   │
│  └──────┬───────┘          └───────┬───────┘                                │
│         │                          │                                         │
│         │ 1:N                      │ 1:N                                    │
│         │                          │                                         │
│  ┌──────▼───────┐          ┌───────▼─────────┐       ┌───────────────┐     │
│  │activity_logs │          │ request_metrics │       │ server_stats  │     │
│  ├──────────────┤          ├─────────────────┤       ├───────────────┤     │
│  │ id (PK)      │          │ id (PK)         │       │ id (PK)       │     │
│  │ user_id (FK) │          │ tunnel_id (FK)  │       │ active_tunnels│     │
│  │ action       │          │ tunnel_name     │       │ total_conns   │     │
│  │ details      │          │ request_path    │       │ bytes_in      │     │
│  │ ip_address   │          │ request_method  │       │ bytes_out     │     │
│  │ created_at   │          │ status_code     │       │ timestamp     │     │
│  └──────────────┘          │ response_time_ms│       └───────────────┘     │
│                            │ bytes_sent      │                              │
│                            │ bytes_received  │                              │
│                            │ client_ip       │                              │
│                            │ timestamp       │                              │
│                            └─────────────────┘                              │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Tables

### users

Stores user accounts for both admin and regular users.

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    is_admin INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    max_tunnels INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO | Unique identifier |
| `email` | TEXT | UNIQUE, NOT NULL | User's email address |
| `password_hash` | TEXT | NOT NULL | bcrypt hashed password |
| `token` | TEXT | UNIQUE, NOT NULL | 64-char hex tunnel auth token |
| `is_admin` | INTEGER | DEFAULT 0 | 1 = admin, 0 = regular user |
| `is_active` | INTEGER | DEFAULT 1 | 1 = enabled, 0 = disabled |
| `max_tunnels` | INTEGER | DEFAULT 10 | Maximum allowed tunnels |
| `created_at` | TIMESTAMP | DEFAULT NOW | Account creation time |
| `last_login` | TIMESTAMP | NULL | Last successful login |

**Indexes:**
- Unique index on `email`
- Unique index on `token`

---

### tunnels

Stores tunnel configurations for each user.

```sql
CREATE TABLE tunnels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    subdomain TEXT,
    remote_port INTEGER,
    is_active INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_connected TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, name)
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO | Unique identifier |
| `user_id` | INTEGER | NOT NULL, FK | Owner user ID |
| `name` | TEXT | NOT NULL | Tunnel name |
| `type` | TEXT | NOT NULL | "http", "https", or "tcp" |
| `subdomain` | TEXT | NULL | Subdomain for HTTP/HTTPS |
| `remote_port` | INTEGER | NULL | Port for TCP tunnels |
| `is_active` | INTEGER | DEFAULT 0 | 1 = connected, 0 = offline |
| `created_at` | TIMESTAMP | DEFAULT NOW | Tunnel creation time |
| `last_connected` | TIMESTAMP | NULL | Last connection time |

**Constraints:**
- Foreign key to `users(id)`
- Unique constraint on `(user_id, name)` - each user can have unique tunnel names

---

### activity_logs

Stores audit trail of user actions.

```sql
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO | Unique identifier |
| `user_id` | INTEGER | NULL, FK | Acting user ID (NULL for system) |
| `action` | TEXT | NOT NULL | Action type (login, user_created, etc.) |
| `details` | TEXT | NULL | Additional details |
| `ip_address` | TEXT | NULL | Client IP address |
| `created_at` | TIMESTAMP | DEFAULT NOW | Action timestamp |

**Action Types:**

| Action | Description |
|--------|-------------|
| `login` | User logged into dashboard |
| `user_created` | New user was created |
| `user_updated` | User settings changed |
| `user_deleted` | User was deleted |
| `token_regenerated` | User's tunnel token changed |

---

### server_stats

Stores server statistics snapshots.

```sql
CREATE TABLE server_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    active_tunnels INTEGER DEFAULT 0,
    total_connections INTEGER DEFAULT 0,
    bytes_in INTEGER DEFAULT 0,
    bytes_out INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO | Unique identifier |
| `active_tunnels` | INTEGER | DEFAULT 0 | Number of active tunnels |
| `total_connections` | INTEGER | DEFAULT 0 | Total connections count |
| `bytes_in` | INTEGER | DEFAULT 0 | Bytes received |
| `bytes_out` | INTEGER | DEFAULT 0 | Bytes transmitted |
| `timestamp` | TIMESTAMP | DEFAULT NOW | Snapshot timestamp |

**Note**: This table is currently created but not actively populated. Future versions may include statistics collection.

---

### tunnel_metrics

Stores aggregate tunnel metrics collected from the frps dashboard API.

```sql
CREATE TABLE tunnel_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tunnel_id INTEGER NOT NULL,
    tunnel_name TEXT NOT NULL,
    traffic_in INTEGER DEFAULT 0,
    traffic_out INTEGER DEFAULT 0,
    current_connections INTEGER DEFAULT 0,
    status TEXT DEFAULT 'offline',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tunnel_id) REFERENCES tunnels(id)
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO | Unique identifier |
| `tunnel_id` | INTEGER | NOT NULL, FK | Reference to tunnel |
| `tunnel_name` | TEXT | NOT NULL | Tunnel name (denormalized) |
| `traffic_in` | INTEGER | DEFAULT 0 | Bytes received today |
| `traffic_out` | INTEGER | DEFAULT 0 | Bytes transmitted today |
| `current_connections` | INTEGER | DEFAULT 0 | Active connections |
| `status` | TEXT | DEFAULT 'offline' | 'online' or 'offline' |
| `collected_at` | TIMESTAMP | DEFAULT NOW | Collection timestamp |

**Indexes:**
- `idx_tunnel_metrics_tunnel` on `(tunnel_id, collected_at)`

**Note**: This table is populated by a background task that polls the frps dashboard API every 60 seconds.

---

### request_metrics

Stores per-request metrics reported by tunnel clients for performance monitoring.

```sql
CREATE TABLE request_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tunnel_id INTEGER NOT NULL,
    tunnel_name TEXT NOT NULL,
    request_path TEXT,
    request_method TEXT,
    status_code INTEGER,
    response_time_ms INTEGER,
    bytes_sent INTEGER DEFAULT 0,
    bytes_received INTEGER DEFAULT 0,
    client_ip TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tunnel_id) REFERENCES tunnels(id)
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTO | Unique identifier |
| `tunnel_id` | INTEGER | NOT NULL, FK | Reference to tunnel |
| `tunnel_name` | TEXT | NOT NULL | Tunnel name (denormalized) |
| `request_path` | TEXT | NULL | URL path of request |
| `request_method` | TEXT | NULL | HTTP method (GET, POST, etc.) |
| `status_code` | INTEGER | NULL | HTTP response status code |
| `response_time_ms` | INTEGER | NULL | Response time in milliseconds |
| `bytes_sent` | INTEGER | DEFAULT 0 | Request body size |
| `bytes_received` | INTEGER | DEFAULT 0 | Response body size |
| `client_ip` | TEXT | NULL | Client IP address |
| `timestamp` | TIMESTAMP | DEFAULT NOW | Request timestamp |

**Indexes:**
- `idx_request_metrics_tunnel` on `(tunnel_id, timestamp)`
- `idx_request_metrics_slow` on `(response_time_ms DESC)`

**Data Retention**: Metrics older than 7 days are automatically cleaned up by a background task.

---

## Relationships

### users → tunnels (One-to-Many)

Each user can have multiple tunnels:

```sql
-- Get all tunnels for a user
SELECT t.*, u.email
FROM tunnels t
JOIN users u ON t.user_id = u.id
WHERE u.id = 1;
```

### users → activity_logs (One-to-Many)

Each user can have multiple activity log entries:

```sql
-- Get all activity for a user
SELECT a.*, u.email
FROM activity_logs a
LEFT JOIN users u ON a.user_id = u.id
WHERE u.id = 1
ORDER BY a.created_at DESC;
```

### Cascade Behavior

When a user is deleted:

```sql
-- Application handles cascade manually
DELETE FROM tunnels WHERE user_id = ?;
DELETE FROM users WHERE id = ? AND is_admin = 0;
```

Activity logs are NOT deleted when a user is deleted (preserved for audit trail).

---

## Common Queries

### User Management

```sql
-- List all non-admin users with tunnel counts
SELECT
    u.id,
    u.email,
    u.is_active,
    u.max_tunnels,
    u.created_at,
    u.last_login,
    COUNT(t.id) as tunnel_count
FROM users u
LEFT JOIN tunnels t ON u.id = t.user_id
WHERE u.is_admin = 0
GROUP BY u.id
ORDER BY u.created_at DESC;

-- Find user by email
SELECT * FROM users WHERE email = 'user@example.com';

-- Find user by token
SELECT * FROM users WHERE token = 'abc123...';

-- Get admin users
SELECT * FROM users WHERE is_admin = 1;

-- Get active users
SELECT * FROM users WHERE is_active = 1 AND is_admin = 0;
```

### Tunnel Management

```sql
-- List all active tunnels with user info
SELECT
    t.*,
    u.email as user_email
FROM tunnels t
JOIN users u ON t.user_id = u.id
WHERE t.is_active = 1;

-- Count tunnels per user
SELECT
    u.email,
    u.max_tunnels,
    COUNT(t.id) as current_tunnels,
    (u.max_tunnels - COUNT(t.id)) as remaining
FROM users u
LEFT JOIN tunnels t ON u.id = t.user_id
GROUP BY u.id;

-- Find duplicate subdomains
SELECT subdomain, COUNT(*) as count
FROM tunnels
WHERE subdomain IS NOT NULL
GROUP BY subdomain
HAVING count > 1;
```

### Statistics

```sql
-- User statistics
SELECT
    COUNT(*) as total_users,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_users,
    SUM(CASE WHEN is_admin = 1 THEN 1 ELSE 0 END) as admin_users
FROM users;

-- Tunnel statistics
SELECT
    COUNT(*) as total_tunnels,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_tunnels,
    SUM(CASE WHEN type = 'http' THEN 1 ELSE 0 END) as http_tunnels,
    SUM(CASE WHEN type = 'tcp' THEN 1 ELSE 0 END) as tcp_tunnels
FROM tunnels;

-- Recent activity (last 24 hours)
SELECT * FROM activity_logs
WHERE created_at >= datetime('now', '-1 day')
ORDER BY created_at DESC;

-- Login frequency by user
SELECT
    u.email,
    COUNT(a.id) as login_count,
    MAX(a.created_at) as last_login
FROM users u
LEFT JOIN activity_logs a ON u.id = a.user_id AND a.action = 'login'
GROUP BY u.id
ORDER BY login_count DESC;
```

### Cleanup Queries

```sql
-- Delete old activity logs (older than 30 days)
DELETE FROM activity_logs
WHERE created_at < datetime('now', '-30 days');

-- Remove orphaned tunnels (user deleted)
DELETE FROM tunnels
WHERE user_id NOT IN (SELECT id FROM users);

-- Reset all tunnel statuses to offline
UPDATE tunnels SET is_active = 0;
```

---

## Data Management

### Backup

```bash
# Simple file copy (when database is not in use)
cp tunnel.db tunnel_backup_$(date +%Y%m%d).db

# SQLite backup command (safe for live databases)
sqlite3 tunnel.db ".backup 'tunnel_backup.db'"

# Dump as SQL
sqlite3 tunnel.db .dump > tunnel_dump.sql
```

### Restore

```bash
# From backup file
cp tunnel_backup.db tunnel.db

# From SQL dump
sqlite3 tunnel.db < tunnel_dump.sql
```

### Export Data

```bash
# Export users to CSV
sqlite3 -header -csv tunnel.db \
    "SELECT id, email, is_admin, is_active, max_tunnels, created_at FROM users;" \
    > users.csv

# Export activity logs to CSV
sqlite3 -header -csv tunnel.db \
    "SELECT * FROM activity_logs ORDER BY created_at DESC;" \
    > activity.csv
```

### Database Maintenance

```bash
# Check database integrity
sqlite3 tunnel.db "PRAGMA integrity_check;"

# Analyze for query optimization
sqlite3 tunnel.db "ANALYZE;"

# Vacuum to reclaim space
sqlite3 tunnel.db "VACUUM;"

# Check database size
ls -lh tunnel.db
```

---

## Migration

### Adding New Columns

```sql
-- Example: Add a 'notes' column to users
ALTER TABLE users ADD COLUMN notes TEXT;

-- Example: Add 'bandwidth_limit' to users
ALTER TABLE users ADD COLUMN bandwidth_limit INTEGER DEFAULT 0;
```

### Creating Indexes

```sql
-- Index for faster email lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Index for faster token lookups
CREATE INDEX IF NOT EXISTS idx_users_token ON users(token);

-- Index for activity log queries
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_logs(user_id);
```

### Schema Migration Script

```python
# Example migration script
import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "./tunnel.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check current schema version (you'd need to add this table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        )
    """)

    cursor.execute("SELECT MAX(version) FROM schema_version")
    current_version = cursor.fetchone()[0] or 0

    # Migration 1: Add notes column
    if current_version < 1:
        cursor.execute("ALTER TABLE users ADD COLUMN notes TEXT")
        cursor.execute("INSERT INTO schema_version VALUES (1)")
        print("Migration 1 applied")

    # Migration 2: Add indexes
    if current_version < 2:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("INSERT INTO schema_version VALUES (2)")
        print("Migration 2 applied")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
```

---

## Performance Considerations

### Query Optimization

1. **Use indexes** for frequently queried columns
2. **Limit results** with `LIMIT` clause
3. **Avoid SELECT \*** - specify needed columns
4. **Use JOINs** instead of multiple queries

### Connection Management

The application uses a new connection for each request:

```python
conn = sqlite3.connect(DB_FILE)
# ... operations ...
conn.close()
```

For higher performance, consider:
- Connection pooling
- WAL (Write-Ahead Logging) mode

```sql
PRAGMA journal_mode=WAL;
```

### Size Limits

SQLite practical limits:

| Metric | Limit |
|--------|-------|
| Database size | 281 TB (theoretical) |
| Rows per table | 2^64 |
| Columns per table | 2000 |
| Query complexity | Reasonable |

For this application, SQLite should handle:
- Thousands of users
- Tens of thousands of tunnels
- Millions of activity logs

---

## Related Documentation

- [Architecture](../architecture/README.md) - System design
- [API Reference](../api/README.md) - Endpoint details
- [Configuration](../configuration/README.md) - DB path settings
- [Deployment](../deployment/README.md) - Production setup
