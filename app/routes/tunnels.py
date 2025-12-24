"""
Tunnel management routes
"""
import sqlite3
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from ..config import DB_FILE
from ..models.schemas import TunnelCreate, TunnelStatusUpdate, TunnelUpdate
from ..dependencies import verify_token
from ..services.tunnel import (
    get_server_domain,
    get_public_url,
    check_user_quota,
    generate_frpc_config,
)
from ..services.activity import log_activity

router = APIRouter(tags=["tunnels"])


@router.get("")
async def list_tunnels(user_id: int = Depends(verify_token)):
    """List user's tunnels or all tunnels (admin)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if admin
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    is_admin = cursor.fetchone()[0]

    if is_admin:
        # Show all tunnels for admin
        cursor.execute("""
            SELECT t.*, u.email as user_email
            FROM tunnels t
            JOIN users u ON t.user_id = u.id
            ORDER BY t.created_at DESC
        """)
    else:
        # Show only user's tunnels
        cursor.execute("""
            SELECT * FROM tunnels
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))

    tunnels = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Add public_url to each tunnel
    domain = get_server_domain()
    for t in tunnels:
        t['public_url'] = get_public_url(t['type'], t.get('subdomain'), t.get('remote_port'), domain)

    return {"tunnels": tunnels}


@router.post("")
async def create_tunnel(tunnel: TunnelCreate, user_id: int = Depends(verify_token)):
    """Create a new tunnel for the authenticated user"""
    # Check quota
    can_create, current_count, max_tunnels = check_user_quota(user_id)
    if not can_create:
        raise HTTPException(
            status_code=400,
            detail=f"Tunnel quota exceeded. You have {current_count}/{max_tunnels} tunnels."
        )

    # Validate tunnel type
    if tunnel.type not in ("http", "https", "tcp"):
        raise HTTPException(status_code=400, detail="Invalid tunnel type. Must be http, https, or tcp.")

    # For http/https, subdomain is required
    if tunnel.type in ("http", "https") and not tunnel.subdomain:
        raise HTTPException(status_code=400, detail="Subdomain is required for HTTP/HTTPS tunnels.")

    # For tcp, remote_port is required
    if tunnel.type == "tcp" and not tunnel.remote_port:
        raise HTTPException(status_code=400, detail="Remote port is required for TCP tunnels.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO tunnels (user_id, name, type, local_port, local_host, subdomain, remote_port)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, tunnel.name, tunnel.type, tunnel.local_port, tunnel.local_host,
              tunnel.subdomain, tunnel.remote_port))

        tunnel_id = cursor.lastrowid
        conn.commit()

        log_activity(user_id, "tunnel_created", f"Created tunnel '{tunnel.name}' ({tunnel.type})")

        domain = get_server_domain()
        public_url = get_public_url(tunnel.type, tunnel.subdomain, tunnel.remote_port, domain)

        # Generate frpc config snippet
        frpc_config = generate_frpc_config(tunnel, domain)

        return {
            "id": tunnel_id,
            "name": tunnel.name,
            "type": tunnel.type,
            "local_port": tunnel.local_port,
            "local_host": tunnel.local_host,
            "subdomain": tunnel.subdomain,
            "remote_port": tunnel.remote_port,
            "public_url": public_url,
            "frpc_config": frpc_config
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Tunnel with name '{tunnel.name}' already exists.")
    finally:
        conn.close()


@router.put("/{tunnel_id}")
async def update_tunnel(tunnel_id: int, tunnel_update: TunnelUpdate, user_id: int = Depends(verify_token)):
    """Update a tunnel configuration (must own the tunnel or be admin)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if admin
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    is_admin = cursor.fetchone()[0]

    # Get existing tunnel
    cursor.execute("SELECT * FROM tunnels WHERE id = ?", (tunnel_id,))
    tunnel = cursor.fetchone()

    if not tunnel:
        conn.close()
        raise HTTPException(status_code=404, detail="Tunnel not found")

    # Check ownership
    if not is_admin and tunnel['user_id'] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="You don't have permission to update this tunnel")

    # Build update fields
    update_fields = {}
    if tunnel_update.name is not None:
        update_fields['name'] = tunnel_update.name
    if tunnel_update.type is not None:
        update_fields['type'] = tunnel_update.type
    if tunnel_update.local_port is not None:
        update_fields['local_port'] = tunnel_update.local_port
    if tunnel_update.local_host is not None:
        update_fields['local_host'] = tunnel_update.local_host
    if tunnel_update.subdomain is not None:
        update_fields['subdomain'] = tunnel_update.subdomain
    if tunnel_update.remote_port is not None:
        update_fields['remote_port'] = tunnel_update.remote_port

    if not update_fields:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")

    # Determine final type for validation
    final_type = update_fields.get('type', tunnel['type'])
    final_subdomain = update_fields.get('subdomain', tunnel['subdomain'])
    final_remote_port = update_fields.get('remote_port', tunnel['remote_port'])

    # Validate type constraints
    if final_type in ("http", "https") and not final_subdomain:
        conn.close()
        raise HTTPException(status_code=400, detail="Subdomain is required for HTTP/HTTPS tunnels.")
    if final_type == "tcp" and not final_remote_port:
        conn.close()
        raise HTTPException(status_code=400, detail="Remote port is required for TCP tunnels.")

    # Build and execute UPDATE query
    set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
    values = list(update_fields.values()) + [tunnel_id]

    try:
        cursor.execute(f"UPDATE tunnels SET {set_clause} WHERE id = ?", values)
        conn.commit()

        # Fetch updated tunnel
        cursor.execute("SELECT * FROM tunnels WHERE id = ?", (tunnel_id,))
        updated_tunnel = dict(cursor.fetchone())
        conn.close()

        log_activity(user_id, "tunnel_updated", f"Updated tunnel '{updated_tunnel['name']}'")

        domain = get_server_domain()
        updated_tunnel['public_url'] = get_public_url(
            updated_tunnel['type'],
            updated_tunnel.get('subdomain'),
            updated_tunnel.get('remote_port'),
            domain
        )

        return updated_tunnel
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Tunnel with name '{update_fields.get('name')}' already exists.")


@router.delete("/{tunnel_id}")
async def delete_tunnel(tunnel_id: int, user_id: int = Depends(verify_token)):
    """Delete a tunnel (must own the tunnel or be admin)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if admin
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    is_admin = cursor.fetchone()[0]

    # Get tunnel info
    cursor.execute("SELECT * FROM tunnels WHERE id = ?", (tunnel_id,))
    tunnel = cursor.fetchone()

    if not tunnel:
        conn.close()
        raise HTTPException(status_code=404, detail="Tunnel not found")

    # Check ownership
    if not is_admin and tunnel['user_id'] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="You don't have permission to delete this tunnel")

    # Delete tunnel
    cursor.execute("DELETE FROM tunnels WHERE id = ?", (tunnel_id,))
    conn.commit()
    conn.close()

    log_activity(user_id, "tunnel_deleted", f"Deleted tunnel '{tunnel['name']}'")

    return {"message": "Tunnel deleted successfully"}


@router.put("/{tunnel_id}/status")
async def update_tunnel_status(tunnel_id: int, status: TunnelStatusUpdate, user_id: int = Depends(verify_token)):
    """Update tunnel active status (used by client to report connection state)"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get tunnel info
    cursor.execute("SELECT * FROM tunnels WHERE id = ?", (tunnel_id,))
    tunnel = cursor.fetchone()

    if not tunnel:
        conn.close()
        raise HTTPException(status_code=404, detail="Tunnel not found")

    # Check ownership
    if tunnel['user_id'] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="You don't have permission to update this tunnel")

    # Update status
    now = datetime.utcnow() if status.is_active else None
    cursor.execute("""
        UPDATE tunnels
        SET is_active = ?, last_connected = COALESCE(?, last_connected)
        WHERE id = ?
    """, (int(status.is_active), now, tunnel_id))
    conn.commit()
    conn.close()

    return {"message": "Tunnel status updated", "is_active": status.is_active}


@router.get("/{tunnel_id}/config")
async def get_tunnel_config(tunnel_id: int, user_id: int = Depends(verify_token)):
    """Get frpc configuration for a specific tunnel"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get tunnel info
    cursor.execute("SELECT * FROM tunnels WHERE id = ?", (tunnel_id,))
    tunnel = cursor.fetchone()

    if not tunnel:
        conn.close()
        raise HTTPException(status_code=404, detail="Tunnel not found")

    # Check ownership (admins can view any config)
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    is_admin = cursor.fetchone()[0]

    if not is_admin and tunnel['user_id'] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="You don't have permission to view this tunnel config")

    # Get user's tunnel token
    cursor.execute("SELECT token FROM users WHERE id = ?", (tunnel['user_id'],))
    user_token = cursor.fetchone()[0]

    conn.close()

    domain = get_server_domain()

    # Create a TunnelCreate-like object for config generation
    tunnel_data = TunnelCreate(
        name=tunnel['name'],
        type=tunnel['type'],
        local_port=tunnel['local_port'],
        local_host=tunnel['local_host'] or '127.0.0.1',
        subdomain=tunnel['subdomain'],
        remote_port=tunnel['remote_port']
    )

    frpc_config = generate_frpc_config(tunnel_data, domain, include_common=True, user_token=user_token)
    public_url = get_public_url(tunnel['type'], tunnel['subdomain'], tunnel['remote_port'], domain)

    return {
        "tunnel_id": tunnel_id,
        "name": tunnel['name'],
        "public_url": public_url,
        "frpc_config": frpc_config
    }
