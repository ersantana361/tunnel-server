"""
Statistics and activity log routes
"""
import sqlite3
from fastapi import APIRouter, Depends

from ..config import DB_FILE
from ..dependencies import verify_admin

router = APIRouter(tags=["stats"])


@router.get("/stats")
async def get_stats(admin_id: int = Depends(verify_admin)):
    """Get server statistics (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # User stats
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE is_admin = 0")
    total_users = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as active FROM users WHERE is_admin = 0 AND is_active = 1")
    active_users = cursor.fetchone()['active']

    # Tunnel stats
    cursor.execute("SELECT COUNT(*) as total FROM tunnels")
    total_tunnels = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as active FROM tunnels WHERE is_active = 1")
    active_tunnels = cursor.fetchone()['active']

    # Recent activity
    cursor.execute("""
        SELECT a.*, u.email
        FROM activity_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
        LIMIT 10
    """)
    recent_activity = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "users": {"total": total_users, "active": active_users},
        "tunnels": {"total": total_tunnels, "active": active_tunnels},
        "recent_activity": recent_activity
    }


@router.get("/activity")
async def get_activity(admin_id: int = Depends(verify_admin), limit: int = 50):
    """Get activity logs (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*, u.email
        FROM activity_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
        LIMIT ?
    """, (limit,))

    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"logs": logs}
