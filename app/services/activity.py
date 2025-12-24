"""
Activity logging service
"""
import sqlite3
from typing import Optional
from ..config import DB_FILE


def log_activity(user_id: Optional[int], action: str, details: str = "", ip: str = ""):
    """Log user activity to database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO activity_logs (user_id, action, details, ip_address)
        VALUES (?, ?, ?, ?)
    """, (user_id, action, details, ip))
    conn.commit()
    conn.close()
