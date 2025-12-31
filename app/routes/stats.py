"""
Statistics and activity log routes
"""
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends

from ..config import DB_FILE
from ..dependencies import verify_admin, verify_token
from ..models.schemas import MetricsBatch
from ..services import metrics as metrics_service

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


@router.get("/metrics/overview")
async def get_metrics_overview(admin_id: int = Depends(verify_admin)):
    """Get high-level metrics overview from frps and database"""
    return metrics_service.get_metrics_overview()


@router.get("/metrics/tunnels")
async def get_all_tunnels_metrics(user_id: int = Depends(verify_token)):
    """Get all tunnels with their 1-hour request metrics summary"""
    return {"tunnels": metrics_service.get_tunnels_with_request_metrics()}


@router.get("/metrics/tunnels/{tunnel_id}")
async def get_tunnel_metrics(
    tunnel_id: int,
    hours: int = 24,
    admin_id: int = Depends(verify_admin)
):
    """Get metrics for a specific tunnel (admin only)"""
    return metrics_service.get_tunnel_stats(tunnel_id, hours)


@router.get("/metrics/summary")
async def get_metrics_summary(
    tunnel_name: Optional[str] = None,
    period: str = "1h",
    user_id: int = Depends(verify_token)
):
    """
    Get aggregated statistics for a time period.

    Query Parameters:
    - tunnel_name: Filter by tunnel (all if omitted)
    - period: Time window: '1h', '24h', '7d' (default: '1h')
    """
    if period not in ("1h", "24h", "7d"):
        period = "1h"
    return metrics_service.get_metrics_summary(tunnel_name=tunnel_name, period=period)


@router.get("/metrics")
async def get_metrics(
    tunnel_name: Optional[str] = None,
    min_response_time: Optional[int] = None,
    max_response_time: Optional[int] = None,
    status_code: Optional[int] = None,
    method: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user_id: int = Depends(verify_token)
):
    """
    Query stored request metrics with filtering and pagination.

    Query Parameters:
    - tunnel_name: Filter by tunnel name
    - min_response_time: Only requests slower than N ms
    - max_response_time: Only requests faster than N ms
    - status_code: Filter by HTTP status code
    - method: Filter by HTTP method (GET, POST, etc.)
    - limit: Max results (1-1000, default: 100)
    - offset: Pagination offset (default: 0)
    """
    return metrics_service.get_request_metrics(
        tunnel_name=tunnel_name,
        limit=limit,
        offset=offset,
        min_response_time=min_response_time,
        max_response_time=max_response_time,
        status_code=status_code,
        method=method
    )


@router.get("/metrics/requests")
async def get_request_metrics_legacy(
    tunnel_id: Optional[int] = None,
    tunnel_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    min_response_time: Optional[int] = None,
    max_response_time: Optional[int] = None,
    status_code: Optional[int] = None,
    method: Optional[str] = None,
    admin_id: int = Depends(verify_admin)
):
    """Get request-level metrics with optional filters (admin only, legacy endpoint)"""
    result = metrics_service.get_request_metrics(
        tunnel_id=tunnel_id,
        tunnel_name=tunnel_name,
        limit=limit,
        offset=offset,
        min_response_time=min_response_time,
        max_response_time=max_response_time,
        status_code=status_code,
        method=method
    )
    # Return in legacy format for dashboard compatibility
    return {"requests": result["metrics"]}


@router.get("/metrics/slow-requests")
async def get_slow_requests(
    threshold_ms: int = 1000,
    limit: int = 50,
    admin_id: int = Depends(verify_admin)
):
    """Get slow requests across all tunnels"""
    return {
        "threshold_ms": threshold_ms,
        "requests": metrics_service.get_slow_requests(threshold_ms, limit)
    }


@router.post("/metrics/report")
async def report_metrics(
    batch: MetricsBatch,
    user_id: int = Depends(verify_token)
):
    """
    Receive metrics batch from client.
    Clients authenticate with their user token (not admin required).
    """
    stored = metrics_service.store_request_metrics(
        [m.model_dump() for m in batch.metrics],
        user_id
    )
    return {"stored": stored}
