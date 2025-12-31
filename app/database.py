"""
Database initialization and connection management
"""
import sqlite3
import os
import secrets
import bcrypt
from .config import DB_FILE, ADMIN_PASSWORD, ADMIN_TOKEN


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with tables and default admin"""
    # Ensure directory exists
    db_dir = os.path.dirname(DB_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            is_admin INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            max_tunnels INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # Tunnels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tunnels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            local_port INTEGER NOT NULL,
            local_host TEXT DEFAULT '127.0.0.1',
            subdomain TEXT,
            remote_port INTEGER,
            is_active INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_connected TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, name)
        )
    """)

    # Activity logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Server stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS server_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            active_tunnels INTEGER DEFAULT 0,
            total_connections INTEGER DEFAULT 0,
            bytes_in INTEGER DEFAULT 0,
            bytes_out INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tunnel metrics (aggregate stats from frps API)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tunnel_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tunnel_id INTEGER NOT NULL,
            tunnel_name TEXT NOT NULL,
            traffic_in INTEGER DEFAULT 0,
            traffic_out INTEGER DEFAULT 0,
            current_connections INTEGER DEFAULT 0,
            status TEXT DEFAULT 'offline',
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tunnel_id) REFERENCES tunnels(id)
        )
    """)

    # Request metrics (per-request data from client reports)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_metrics (
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
        )
    """)

    # Indexes for efficient querying
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tunnel_metrics_tunnel
        ON tunnel_metrics(tunnel_id, collected_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_request_metrics_tunnel
        ON request_metrics(tunnel_id, timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_request_metrics_slow
        ON request_metrics(response_time_ms DESC)
    """)

    # Create default admin if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    if cursor.fetchone()[0] == 0:
        # Use provided credentials from 1Password (via env vars) or auto-generate
        if ADMIN_PASSWORD and ADMIN_TOKEN:
            # Credentials provided via environment (e.g., from 1Password)
            admin_password = ADMIN_PASSWORD
            admin_token = ADMIN_TOKEN
            password_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt())

            cursor.execute("""
                INSERT INTO users (email, password_hash, token, is_admin, max_tunnels)
                VALUES (?, ?, ?, 1, 999)
            """, ("admin@localhost", password_hash, admin_token))

            print(f"\n{'='*60}")
            print("Admin account created with provided credentials")
            print(f"{'='*60}")
            print(f"Email: admin@localhost")
            print(f"Password: (from ADMIN_PASSWORD env var)")
            print(f"Token: (from ADMIN_TOKEN env var)")
            print(f"{'='*60}\n")
        else:
            # Auto-generate credentials (legacy behavior)
            admin_password = secrets.token_urlsafe(16)
            password_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt())
            admin_token = secrets.token_hex(32)

            cursor.execute("""
                INSERT INTO users (email, password_hash, token, is_admin, max_tunnels)
                VALUES (?, ?, ?, 1, 999)
            """, ("admin@localhost", password_hash, admin_token))

            print(f"\n{'='*60}")
            print("ADMIN CREDENTIALS - SAVE THESE!")
            print(f"{'='*60}")
            print(f"Email: admin@localhost")
            print(f"Password: {admin_password}")
            print(f"Token: {admin_token}")
            print(f"{'='*60}\n")

    conn.commit()
    conn.close()
