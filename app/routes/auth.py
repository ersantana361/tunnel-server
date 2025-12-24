"""
Authentication routes
"""
import sqlite3
from datetime import datetime
from fastapi import APIRouter, HTTPException
import bcrypt

from ..config import DB_FILE
from ..models.schemas import UserLogin
from ..services.auth import create_access_token
from ..services.activity import log_activity

router = APIRouter(tags=["auth"])


@router.post("/login")
async def login(user: UserLogin):
    """Admin/user login"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))
    db_user = cursor.fetchone()

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.checkpw(user.password.encode(), db_user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not db_user['is_active']:
        raise HTTPException(status_code=401, detail="Account disabled")

    # Update last login
    cursor.execute("UPDATE users SET last_login = ? WHERE id = ?",
                   (datetime.utcnow(), db_user['id']))
    conn.commit()
    conn.close()

    # Create JWT token
    access_token = create_access_token({"sub": str(db_user['id'])})

    log_activity(db_user['id'], "login", f"User {user.email} logged in")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user['id'],
            "email": db_user['email'],
            "is_admin": bool(db_user['is_admin']),
            "tunnel_token": db_user['token']
        }
    }
