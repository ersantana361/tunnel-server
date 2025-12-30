"""
Configuration settings for Tunnel Server
"""
import os
import secrets

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Database Configuration
DB_FILE = os.getenv("DB_PATH", "./tunnel.db")

# frp Configuration
FRPS_CONFIG = os.getenv("FRPS_CONFIG", "/etc/frp/frps.ini")

# Admin Credentials (optional, for 1Password integration)
# If set, these will be used instead of auto-generating on first run
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

# Netlify DNS Configuration (for automatic DNS record creation)
NETLIFY_API_TOKEN = os.getenv("NETLIFY_API_TOKEN")
NETLIFY_DNS_ZONE_ID = os.getenv("NETLIFY_DNS_ZONE_ID")  # Zone ID for ersantana.com
TUNNEL_DOMAIN = os.getenv("TUNNEL_DOMAIN", "tunnel.ersantana.com")
