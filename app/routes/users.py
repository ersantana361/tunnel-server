"""
User management routes
"""
import sqlite3
import secrets
from fastapi import APIRouter, HTTPException, Depends
import bcrypt

from ..config import DB_FILE
from ..models.schemas import UserCreate, UserUpdate
from ..dependencies import verify_admin
from ..services.activity import log_activity

router = APIRouter(tags=["users"])


@router.post("")
async def create_user(user: UserCreate, admin_id: int = Depends(verify_admin)):
    """Create new user (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        password_hash = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
        tunnel_token = secrets.token_hex(32)

        cursor.execute("""
            INSERT INTO users (email, password_hash, token, max_tunnels)
            VALUES (?, ?, ?, ?)
        """, (user.email, password_hash, tunnel_token, user.max_tunnels))

        user_id = cursor.lastrowid
        conn.commit()

        log_activity(admin_id, "user_created", f"Created user {user.email}")

        return {
            "id": user_id,
            "email": user.email,
            "tunnel_token": tunnel_token,
            "max_tunnels": user.max_tunnels
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")
    finally:
        conn.close()


@router.get("")
async def list_users(admin_id: int = Depends(verify_admin)):
    """List all users (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.id, u.email, u.token, u.is_admin, u.is_active, u.max_tunnels,
               u.created_at, u.last_login,
               COUNT(t.id) as active_tunnels
        FROM users u
        LEFT JOIN tunnels t ON u.id = t.user_id AND t.is_active = 1
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """)

    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"users": users}


@router.put("/{user_id}")
async def update_user(user_id: int, update: UserUpdate, admin_id: int = Depends(verify_admin)):
    """Update user (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    updates = []
    params = []

    if update.is_active is not None:
        updates.append("is_active = ?")
        params.append(int(update.is_active))

    if update.max_tunnels is not None:
        updates.append("max_tunnels = ?")
        params.append(update.max_tunnels)

    if updates:
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    conn.close()

    log_activity(admin_id, "user_updated", f"Updated user {user_id}")

    return {"message": "User updated successfully"}


@router.delete("/{user_id}")
async def delete_user(user_id: int, admin_id: int = Depends(verify_admin)):
    """Delete user (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Delete user's tunnels first
    cursor.execute("DELETE FROM tunnels WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ? AND is_admin = 0", (user_id,))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete admin or user not found")

    conn.commit()
    conn.close()

    log_activity(admin_id, "user_deleted", f"Deleted user {user_id}")

    return {"message": "User deleted successfully"}


@router.post("/{user_id}/regenerate-token")
async def regenerate_token(user_id: int, admin_id: int = Depends(verify_admin)):
    """Regenerate user's tunnel token (admin only)"""
    new_token = secrets.token_hex(32)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET token = ? WHERE id = ?", (new_token, user_id))
    conn.commit()
    conn.close()

    log_activity(admin_id, "token_regenerated", f"Regenerated token for user {user_id}")

    return {"token": new_token}
