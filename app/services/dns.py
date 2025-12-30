"""
Netlify DNS API integration for automatic DNS record management
"""
import logging
import requests
from typing import Optional

from ..config import NETLIFY_API_TOKEN, NETLIFY_DNS_ZONE_ID, TUNNEL_DOMAIN

logger = logging.getLogger(__name__)

NETLIFY_API_BASE = "https://api.netlify.com/api/v1"


def get_public_ip() -> Optional[str]:
    """Get the server's public IP address"""
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]

    for service in services:
        try:
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                logger.info(f"Detected public IP: {ip}")
                return ip
        except Exception as e:
            logger.debug(f"Failed to get IP from {service}: {e}")
            continue

    logger.error("Failed to detect public IP from any service")
    return None


def _get_headers() -> dict:
    """Get authorization headers for Netlify API"""
    return {
        "Authorization": f"Bearer {NETLIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }


def list_dns_records() -> list:
    """List all DNS records in the zone"""
    if not NETLIFY_API_TOKEN or not NETLIFY_DNS_ZONE_ID:
        logger.warning("Netlify DNS not configured (missing API token or zone ID)")
        return []

    try:
        response = requests.get(
            f"{NETLIFY_API_BASE}/dns_zones/{NETLIFY_DNS_ZONE_ID}/dns_records",
            headers=_get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to list DNS records: {e}")
        return []


def find_record(hostname: str, record_type: str = "A") -> Optional[dict]:
    """Find an existing DNS record by hostname and type"""
    records = list_dns_records()
    for record in records:
        if record.get("hostname") == hostname and record.get("type") == record_type:
            return record
    return None


def create_dns_record(hostname: str, ip: str, record_type: str = "A", ttl: int = 300) -> bool:
    """Create a new DNS record"""
    if not NETLIFY_API_TOKEN or not NETLIFY_DNS_ZONE_ID:
        logger.warning("Netlify DNS not configured (missing API token or zone ID)")
        return False

    try:
        response = requests.post(
            f"{NETLIFY_API_BASE}/dns_zones/{NETLIFY_DNS_ZONE_ID}/dns_records",
            headers=_get_headers(),
            json={
                "type": record_type,
                "hostname": hostname,
                "value": ip,
                "ttl": ttl,
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Created DNS record: {hostname} -> {ip}")
        return True
    except requests.exceptions.HTTPError as e:
        logger.error(f"Failed to create DNS record {hostname}: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Failed to create DNS record {hostname}: {e}")
        return False


def delete_dns_record(record_id: str) -> bool:
    """Delete a DNS record by ID"""
    if not NETLIFY_API_TOKEN or not NETLIFY_DNS_ZONE_ID:
        return False

    try:
        response = requests.delete(
            f"{NETLIFY_API_BASE}/dns_zones/{NETLIFY_DNS_ZONE_ID}/dns_records/{record_id}",
            headers=_get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Deleted DNS record: {record_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete DNS record {record_id}: {e}")
        return False


def update_or_create_record(hostname: str, ip: str, record_type: str = "A", ttl: int = 300) -> bool:
    """Update an existing record or create a new one"""
    existing = find_record(hostname, record_type)

    if existing:
        # Check if IP already matches
        if existing.get("value") == ip:
            logger.info(f"DNS record {hostname} already points to {ip}, skipping")
            return True

        # Delete old record and create new one (Netlify doesn't support PATCH for records)
        logger.info(f"Updating DNS record {hostname}: {existing.get('value')} -> {ip}")
        if delete_dns_record(existing["id"]):
            return create_dns_record(hostname, ip, record_type, ttl)
        return False
    else:
        return create_dns_record(hostname, ip, record_type, ttl)


def setup_tunnel_dns() -> bool:
    """
    Set up DNS records for the tunnel server:
    - tunnel.ersantana.com -> server IP
    - *.tunnel.ersantana.com -> server IP (wildcard)

    Returns True if successful, False otherwise.
    """
    if not NETLIFY_API_TOKEN or not NETLIFY_DNS_ZONE_ID:
        logger.info("Netlify DNS not configured, skipping DNS setup")
        return False

    ip = get_public_ip()
    if not ip:
        logger.error("Could not determine public IP, skipping DNS setup")
        return False

    logger.info(f"Setting up DNS records for {TUNNEL_DOMAIN} pointing to {ip}")

    success = True

    # Create/update the main domain record (tunnel.ersantana.com)
    if not update_or_create_record(TUNNEL_DOMAIN, ip):
        success = False

    # Create/update the wildcard record (*.tunnel.ersantana.com)
    wildcard_hostname = f"*.{TUNNEL_DOMAIN}"
    if not update_or_create_record(wildcard_hostname, ip):
        success = False

    if success:
        logger.info(f"DNS setup complete: {TUNNEL_DOMAIN} and {wildcard_hostname} -> {ip}")
    else:
        logger.warning("DNS setup completed with errors")

    return success
