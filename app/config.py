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
