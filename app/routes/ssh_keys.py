"""
SSH key management routes
"""
import base64
import hashlib
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse

from ..config import DB_FILE
from ..models.schemas import SSHKeyCreate
from ..dependencies import verify_token
from ..services.activity import log_activity

router = APIRouter(tags=["ssh-keys"])


def compute_fingerprint(public_key: str) -> str:
    """Compute SHA256 fingerprint of an SSH public key"""
    # Extract the key data (second field in "type base64data comment" format)
    parts = public_key.strip().split()
    if len(parts) < 2:
        raise ValueError("Invalid SSH public key format")

    key_data = base64.b64decode(parts[1])
    digest = hashlib.sha256(key_data).digest()
    fingerprint = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{fingerprint}"


@router.get("")
async def list_ssh_keys(user_id: int = Depends(verify_token)):
    """List user's SSH keys"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM ssh_keys
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))

    keys = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"keys": keys}


@router.post("")
async def add_ssh_key(key_data: SSHKeyCreate, user_id: int = Depends(verify_token)):
    """Add an SSH public key"""
    public_key = key_data.public_key.strip()

    # Validate key format
    parts = public_key.split()
    if len(parts) < 2 or parts[0] not in (
        "ssh-rsa", "ssh-ed25519", "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521", "ssh-dss"
    ):
        raise HTTPException(status_code=400, detail="Invalid SSH public key format")

    try:
        fingerprint = compute_fingerprint(public_key)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse SSH public key")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO ssh_keys (user_id, name, public_key, fingerprint)
            VALUES (?, ?, ?, ?)
        """, (user_id, key_data.name, public_key, fingerprint))

        key_id = cursor.lastrowid
        conn.commit()

        log_activity(user_id, "ssh_key_added", f"Added SSH key '{key_data.name}' ({fingerprint})")

        return {
            "id": key_id,
            "name": key_data.name,
            "public_key": public_key,
            "fingerprint": fingerprint
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="This SSH key is already registered")
    finally:
        conn.close()


@router.delete("/{key_id}")
async def delete_ssh_key(key_id: int, user_id: int = Depends(verify_token)):
    """Delete an SSH key (must own the key)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ssh_keys WHERE id = ?", (key_id,))
    key = cursor.fetchone()

    if not key:
        conn.close()
        raise HTTPException(status_code=404, detail="SSH key not found")

    if key['user_id'] != user_id:
        # Check if admin
        cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        is_admin = cursor.fetchone()[0]
        if not is_admin:
            conn.close()
            raise HTTPException(status_code=403, detail="You don't have permission to delete this key")

    cursor.execute("DELETE FROM ssh_keys WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()

    log_activity(user_id, "ssh_key_deleted", f"Deleted SSH key '{key['name']}'")

    return {"message": "SSH key deleted successfully"}


@router.get("/authorized_keys")
async def get_authorized_keys(user_id: int = Depends(verify_token)):
    """Get all user's SSH keys in authorized_keys format"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT public_key FROM ssh_keys
        WHERE user_id = ?
        ORDER BY created_at
    """, (user_id,))

    keys = [row['public_key'] for row in cursor.fetchall()]
    conn.close()

    content = "\n".join(keys)
    if content:
        content += "\n"

    return PlainTextResponse(content=content)
