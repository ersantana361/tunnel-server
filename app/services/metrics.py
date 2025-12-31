"""
Metrics collection and aggregation service
"""
import logging
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ..config import DB_FILE
from .frps_api import get_frps_client

logger = logging.getLogger(__name__)


def collect_tunnel_metrics() -> bool:
    """
    Collect current metrics from frps API and store in database.
    Returns True if collection was successful.
    """
    client = get_frps_client()

    # Get all proxy stats from frps
    all_proxies = client.get_all_proxy_stats()
    if not all_proxies:
        logger.debug("No proxy stats available from frps")
        return False

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all tunnels from database to match with frps proxies
    cursor.execute("SELECT id, name, type FROM tunnels")
    tunnels = {row["name"]: dict(row) for row in cursor.fetchall()}

    collected_count = 0
    for proxy_type, proxies in all_proxies.items():
        for proxy in proxies:
            proxy_name = proxy.get("name", "")
            if proxy_name in tunnels:
                tunnel = tunnels[proxy_name]
                cursor.execute("""
                    INSERT INTO tunnel_metrics
                    (tunnel_id, tunnel_name, traffic_in, traffic_out,
                     current_connections, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tunnel["id"],
                    tunnel["name"],
                    proxy.get("todayTrafficIn", 0),
                    proxy.get("todayTrafficOut", 0),
                    proxy.get("curConns", 0),
                    proxy.get("status", "offline")
                ))
                collected_count += 1

    conn.commit()
    conn.close()

    logger.debug(f"Collected metrics for {collected_count} tunnels")
    return collected_count > 0


def get_tunnel_stats(tunnel_id: int, hours: int = 24) -> Dict[str, Any]:
    """
    Get aggregated stats for a specific tunnel.

    Returns dict with:
    - tunnel_id, tunnel_name
    - current_status: 'online' or 'offline'
    - current_connections: current connection count
    - traffic_in_total, traffic_out_total: total bytes in period
    - latest_metric_at: timestamp of most recent metric
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    since = datetime.now() - timedelta(hours=hours)

    # Get latest metric for current status
    cursor.execute("""
        SELECT * FROM tunnel_metrics
        WHERE tunnel_id = ?
        ORDER BY collected_at DESC
        LIMIT 1
    """, (tunnel_id,))
    latest = cursor.fetchone()

    if not latest:
        conn.close()
        return {
            "tunnel_id": tunnel_id,
            "tunnel_name": None,
            "current_status": "unknown",
            "current_connections": 0,
            "traffic_in_total": 0,
            "traffic_out_total": 0,
            "latest_metric_at": None
        }

    # Get aggregated traffic for time period
    cursor.execute("""
        SELECT
            MAX(traffic_in) as max_traffic_in,
            MAX(traffic_out) as max_traffic_out
        FROM tunnel_metrics
        WHERE tunnel_id = ? AND collected_at >= ?
    """, (tunnel_id, since.isoformat()))
    agg = cursor.fetchone()

    conn.close()

    return {
        "tunnel_id": tunnel_id,
        "tunnel_name": latest["tunnel_name"],
        "current_status": latest["status"],
        "current_connections": latest["current_connections"],
        "traffic_in_total": agg["max_traffic_in"] or 0,
        "traffic_out_total": agg["max_traffic_out"] or 0,
        "latest_metric_at": latest["collected_at"]
    }


def get_all_tunnels_stats() -> List[Dict[str, Any]]:
    """Get latest stats for all tunnels"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all tunnels with their latest metrics
    cursor.execute("""
        SELECT t.id, t.name, t.type, t.subdomain, t.is_active,
               m.traffic_in, m.traffic_out, m.current_connections,
               m.status, m.collected_at
        FROM tunnels t
        LEFT JOIN (
            SELECT tunnel_id, traffic_in, traffic_out, current_connections,
                   status, collected_at,
                   ROW_NUMBER() OVER (PARTITION BY tunnel_id ORDER BY collected_at DESC) as rn
            FROM tunnel_metrics
        ) m ON t.id = m.tunnel_id AND m.rn = 1
        ORDER BY t.name
    """)

    results = []
    for row in cursor.fetchall():
        results.append({
            "tunnel_id": row["id"],
            "tunnel_name": row["name"],
            "tunnel_type": row["type"],
            "subdomain": row["subdomain"],
            "is_active": bool(row["is_active"]),
            "traffic_in": row["traffic_in"] or 0,
            "traffic_out": row["traffic_out"] or 0,
            "current_connections": row["current_connections"] or 0,
            "status": row["status"] or "unknown",
            "last_collected": row["collected_at"]
        })

    conn.close()
    return results


def get_request_metrics(
    tunnel_id: Optional[int] = None,
    tunnel_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    min_response_time: Optional[int] = None,
    max_response_time: Optional[int] = None,
    status_code: Optional[int] = None,
    method: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get request-level metrics with pagination.

    Args:
        tunnel_id: Filter by specific tunnel ID (optional)
        tunnel_name: Filter by tunnel name (optional)
        limit: Max number of records to return (1-1000)
        offset: Pagination offset
        min_response_time: Filter for requests slower than N ms
        max_response_time: Filter for requests faster than N ms
        status_code: Filter by HTTP status code
        method: Filter by HTTP method (GET, POST, etc.)

    Returns:
        Dict with metrics list, total count, limit, and offset
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Clamp limit
    limit = max(1, min(limit, 1000))

    # Build WHERE clause
    where_clauses = []
    params = []

    if tunnel_id is not None:
        where_clauses.append("tunnel_id = ?")
        params.append(tunnel_id)

    if tunnel_name is not None:
        where_clauses.append("tunnel_name = ?")
        params.append(tunnel_name)

    if min_response_time is not None:
        where_clauses.append("response_time_ms >= ?")
        params.append(min_response_time)

    if max_response_time is not None:
        where_clauses.append("response_time_ms <= ?")
        params.append(max_response_time)

    if status_code is not None:
        where_clauses.append("status_code = ?")
        params.append(status_code)

    if method is not None:
        where_clauses.append("request_method = ?")
        params.append(method.upper())

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get total count
    cursor.execute(f"SELECT COUNT(*) as total FROM request_metrics WHERE {where_sql}", params)
    total = cursor.fetchone()["total"]

    # Get paginated results
    query = f"""
        SELECT * FROM request_metrics
        WHERE {where_sql}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(query, params + [limit, offset])
    results = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "metrics": results,
        "total": total,
        "limit": limit,
        "offset": offset
    }


def get_slow_requests(threshold_ms: int = 1000, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Find requests slower than threshold across all tunnels.

    Args:
        threshold_ms: Response time threshold in milliseconds
        limit: Max number of records to return
    """
    result = get_request_metrics(min_response_time=threshold_ms, limit=limit)
    return result["metrics"]


def _calculate_percentile(sorted_values: List[int], percentile: int) -> int:
    """Calculate percentile from a sorted list of values."""
    if not sorted_values:
        return 0
    index = int(len(sorted_values) * percentile / 100)
    index = min(index, len(sorted_values) - 1)
    return sorted_values[index]


def get_metrics_summary(
    tunnel_name: Optional[str] = None,
    period: str = "1h"
) -> Dict[str, Any]:
    """
    Get aggregated statistics for a time period.

    Args:
        tunnel_name: Filter by tunnel (all if omitted)
        period: Time window: '1h', '24h', '7d'

    Returns:
        Dict with summary statistics including percentiles
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Parse period
    period_hours = {"1h": 1, "24h": 24, "7d": 168}.get(period, 1)
    since = (datetime.now() - timedelta(hours=period_hours)).isoformat()

    # Build WHERE clause
    where_clauses = ["timestamp >= ?"]
    params = [since]

    if tunnel_name:
        where_clauses.append("tunnel_name = ?")
        params.append(tunnel_name)

    where_sql = " AND ".join(where_clauses)

    # Get basic stats
    cursor.execute(f"""
        SELECT
            COUNT(*) as total_requests,
            AVG(response_time_ms) as avg_response_time,
            MIN(response_time_ms) as min_response_time,
            MAX(response_time_ms) as max_response_time,
            SUM(bytes_sent) as total_bytes_in,
            SUM(bytes_received) as total_bytes_out
        FROM request_metrics
        WHERE {where_sql}
    """, params)
    stats = cursor.fetchone()

    # Get status code counts
    cursor.execute(f"""
        SELECT
            SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) as s2xx,
            SUM(CASE WHEN status_code >= 300 AND status_code < 400 THEN 1 ELSE 0 END) as s3xx,
            SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) as s4xx,
            SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as s5xx
        FROM request_metrics
        WHERE {where_sql}
    """, params)
    status_counts = cursor.fetchone()

    # Get all response times for percentile calculation
    cursor.execute(f"""
        SELECT response_time_ms
        FROM request_metrics
        WHERE {where_sql} AND response_time_ms IS NOT NULL
        ORDER BY response_time_ms
    """, params)
    response_times = [row["response_time_ms"] for row in cursor.fetchall()]

    conn.close()

    total_requests = stats["total_requests"] or 0
    errors = (status_counts["s4xx"] or 0) + (status_counts["s5xx"] or 0)
    error_rate = round(errors / total_requests, 4) if total_requests > 0 else 0
    requests_per_minute = round(total_requests / (period_hours * 60), 2) if total_requests > 0 else 0

    return {
        "tunnel_name": tunnel_name,
        "period": period,
        "total_requests": total_requests,
        "avg_response_time_ms": round(stats["avg_response_time"] or 0, 2),
        "p50_response_time_ms": _calculate_percentile(response_times, 50),
        "p95_response_time_ms": _calculate_percentile(response_times, 95),
        "p99_response_time_ms": _calculate_percentile(response_times, 99),
        "min_response_time_ms": stats["min_response_time"] or 0,
        "max_response_time_ms": stats["max_response_time"] or 0,
        "total_bytes_in": stats["total_bytes_in"] or 0,
        "total_bytes_out": stats["total_bytes_out"] or 0,
        "status_codes": {
            "2xx": status_counts["s2xx"] or 0,
            "3xx": status_counts["s3xx"] or 0,
            "4xx": status_counts["s4xx"] or 0,
            "5xx": status_counts["s5xx"] or 0
        },
        "requests_per_minute": requests_per_minute,
        "error_rate": error_rate
    }


def get_tunnels_with_request_metrics() -> List[Dict[str, Any]]:
    """
    Get all tunnels with their 1-hour request metrics summary.

    Returns list of tunnels with metrics in the format expected by the client.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    since_1h = (datetime.now() - timedelta(hours=1)).isoformat()
    since_5m = (datetime.now() - timedelta(minutes=5)).isoformat()

    # Get all unique tunnel names from request_metrics
    cursor.execute("""
        SELECT DISTINCT tunnel_name FROM request_metrics
        UNION
        SELECT name as tunnel_name FROM tunnels
    """)
    tunnel_names = [row["tunnel_name"] for row in cursor.fetchall()]

    results = []
    for tunnel_name in tunnel_names:
        # Get 1h stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_requests,
                AVG(response_time_ms) as avg_response_time,
                SUM(bytes_sent) as total_bytes_in,
                SUM(bytes_received) as total_bytes_out,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors,
                MAX(timestamp) as last_request
            FROM request_metrics
            WHERE tunnel_name = ? AND timestamp >= ?
        """, (tunnel_name, since_1h))
        stats = cursor.fetchone()

        # Get p95 response time
        cursor.execute("""
            SELECT response_time_ms
            FROM request_metrics
            WHERE tunnel_name = ? AND timestamp >= ? AND response_time_ms IS NOT NULL
            ORDER BY response_time_ms
        """, (tunnel_name, since_1h))
        response_times = [row["response_time_ms"] for row in cursor.fetchall()]
        p95 = _calculate_percentile(response_times, 95)

        # Check if tunnel had recent activity (last 5 min)
        cursor.execute("""
            SELECT COUNT(*) as recent
            FROM request_metrics
            WHERE tunnel_name = ? AND timestamp >= ?
        """, (tunnel_name, since_5m))
        recent = cursor.fetchone()["recent"]

        total = stats["total_requests"] or 0
        errors = stats["errors"] or 0
        error_rate = round(errors / total, 4) if total > 0 else 0

        # Determine status
        if recent > 0:
            status = "active"
        elif stats["last_request"]:
            status = "idle"
        else:
            status = "unknown"

        results.append({
            "tunnel_name": tunnel_name,
            "total_requests_1h": total,
            "avg_response_time_1h": round(stats["avg_response_time"] or 0, 2),
            "p95_response_time_1h": p95,
            "total_bytes_in_1h": stats["total_bytes_in"] or 0,
            "total_bytes_out_1h": stats["total_bytes_out"] or 0,
            "error_rate_1h": error_rate,
            "last_request": stats["last_request"],
            "status": status
        })

    conn.close()

    # Sort by total requests descending
    results.sort(key=lambda x: x["total_requests_1h"], reverse=True)
    return results


def store_request_metrics(metrics: List[Dict[str, Any]], user_id: int) -> int:
    """
    Store a batch of request metrics from client report.

    Args:
        metrics: List of metric dicts with tunnel_name, request_path, etc.
        user_id: ID of the user reporting metrics (for validation)

    Returns:
        Number of metrics stored
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get user's tunnels for validation
    cursor.execute("SELECT id, name FROM tunnels WHERE user_id = ?", (user_id,))
    user_tunnels = {row["name"]: row["id"] for row in cursor.fetchall()}

    stored_count = 0
    for metric in metrics:
        tunnel_name = metric.get("tunnel_name")
        if tunnel_name not in user_tunnels:
            logger.warning(f"User {user_id} tried to report metrics for unknown tunnel: {tunnel_name}")
            continue

        tunnel_id = user_tunnels[tunnel_name]
        cursor.execute("""
            INSERT INTO request_metrics
            (tunnel_id, tunnel_name, request_path, request_method, status_code,
             response_time_ms, bytes_sent, bytes_received, client_ip, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tunnel_id,
            tunnel_name,
            metric.get("request_path", ""),
            metric.get("request_method", ""),
            metric.get("status_code"),
            metric.get("response_time_ms"),
            metric.get("bytes_sent", 0),
            metric.get("bytes_received", 0),
            metric.get("client_ip", ""),
            metric.get("timestamp", datetime.now().isoformat())
        ))
        stored_count += 1

    conn.commit()
    conn.close()

    return stored_count


def get_metrics_overview() -> Dict[str, Any]:
    """
    Get high-level metrics overview combining frps and database data.
    """
    client = get_frps_client()
    server_info = client.get_server_info()

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Count request metrics from last 24 hours
    since = (datetime.now() - timedelta(hours=24)).isoformat()
    cursor.execute("""
        SELECT COUNT(*) as count, AVG(response_time_ms) as avg_time
        FROM request_metrics
        WHERE timestamp >= ?
    """, (since,))
    req_stats = cursor.fetchone()

    # Count slow requests
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM request_metrics
        WHERE timestamp >= ? AND response_time_ms >= 1000
    """, (since,))
    slow_count = cursor.fetchone()["count"]

    conn.close()

    return {
        "frps_available": server_info is not None,
        "frps_info": server_info,
        "requests_24h": req_stats["count"] or 0,
        "avg_response_time_ms": round(req_stats["avg_time"] or 0, 2),
        "slow_requests_24h": slow_count
    }


def cleanup_old_metrics(days: int = 7) -> int:
    """
    Clean up metrics older than specified days.
    Returns number of records deleted.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("DELETE FROM tunnel_metrics WHERE collected_at < ?", (cutoff,))
    deleted_tunnel = cursor.rowcount

    cursor.execute("DELETE FROM request_metrics WHERE timestamp < ?", (cutoff,))
    deleted_request = cursor.rowcount

    conn.commit()
    conn.close()

    total = deleted_tunnel + deleted_request
    if total > 0:
        logger.info(f"Cleaned up {total} old metric records")

    return total
