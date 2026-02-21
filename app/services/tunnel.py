"""
Tunnel services - URL generation, config generation, quota checks
"""
import os
import socket
import sqlite3
from typing import Optional, Tuple, Dict, Any
from ..config import DB_FILE, FRPS_CONFIG
from ..models.schemas import TunnelCreate


def get_server_domain() -> str:
    """Get server domain from frps config or environment"""
    domain = os.getenv("SERVER_DOMAIN", "")
    if domain:
        return domain

    # Try to read from frps.ini
    try:
        if os.path.exists(FRPS_CONFIG):
            with open(FRPS_CONFIG, 'r') as f:
                for line in f:
                    if 'subdomain_host' in line:
                        return line.split('=')[1].strip()
    except:
        pass

    return "localhost"


def get_public_url(
    tunnel_type: str,
    subdomain: Optional[str] = None,
    remote_port: Optional[int] = None,
    domain: Optional[str] = None
) -> Optional[str]:
    """Generate public URL for a tunnel"""
    if domain is None:
        domain = get_server_domain()

    if tunnel_type in ("http", "https"):
        protocol = "https" if tunnel_type == "https" else "http"
        if subdomain:
            return f"{protocol}://{subdomain}.{domain}"
        return f"{protocol}://{domain}"
    elif tunnel_type in ("tcp", "ssh") and remote_port:
        return f"tcp://{domain}:{remote_port}"
    return None


def get_ssh_connection_string(
    ssh_user: str,
    remote_port: int,
    domain: Optional[str] = None
) -> str:
    """Generate SSH connection string for display"""
    if domain is None:
        domain = get_server_domain()
    return f"ssh {ssh_user}@{domain} -p {remote_port}"


def test_ssh_connection(domain: str, remote_port: int) -> Dict[str, Any]:
    """Test if an SSH service is reachable on the given domain:port"""
    result = {"reachable": False, "is_ssh": False, "ssh_banner": None}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((domain, remote_port))
        result["reachable"] = True
        # Try to read SSH banner
        banner = sock.recv(256).decode("utf-8", errors="replace").strip()
        if banner.startswith("SSH-"):
            result["is_ssh"] = True
            result["ssh_banner"] = banner
        sock.close()
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass
    return result


def check_user_quota(user_id: int) -> Tuple[bool, int, int]:
    """
    Check if user can create more tunnels.
    Returns (can_create, current_count, max_allowed)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT max_tunnels FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    max_tunnels = result[0] if result else 10

    cursor.execute("SELECT COUNT(*) FROM tunnels WHERE user_id = ?", (user_id,))
    current_count = cursor.fetchone()[0]

    conn.close()

    return current_count < max_tunnels, current_count, max_tunnels


def generate_frpc_config(
    tunnel: TunnelCreate,
    domain: str,
    include_common: bool = False,
    user_token: Optional[str] = None
) -> str:
    """Generate frpc.ini configuration for a tunnel"""
    config_lines = []

    if include_common:
        config_lines.append("[common]")
        config_lines.append(f"server_addr = {domain}")
        config_lines.append("server_port = 7000")
        if user_token:
            config_lines.append(f"token = {user_token}")
        config_lines.append("")

    config_lines.append(f"[{tunnel.name}]")

    # SSH tunnels map to TCP in frpc (frp has no native SSH type)
    frpc_type = "tcp" if tunnel.type == "ssh" else tunnel.type
    config_lines.append(f"type = {frpc_type}")
    config_lines.append(f"local_ip = {tunnel.local_host}")
    config_lines.append(f"local_port = {tunnel.local_port}")

    if tunnel.type in ("http", "https") and tunnel.subdomain:
        config_lines.append(f"subdomain = {tunnel.subdomain}")
    elif tunnel.type in ("tcp", "ssh") and tunnel.remote_port:
        config_lines.append(f"remote_port = {tunnel.remote_port}")

    return "\n".join(config_lines)
