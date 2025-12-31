"""
frps Dashboard API client for fetching tunnel statistics
"""
import logging
from typing import Optional, Dict, List, Any
import requests
from requests.auth import HTTPBasicAuth

from ..config import (
    FRPS_DASHBOARD_HOST,
    FRPS_DASHBOARD_PORT,
    FRPS_DASHBOARD_USER,
    FRPS_DASHBOARD_PASS,
)

logger = logging.getLogger(__name__)


class FrpsApiClient:
    """Client for querying the frps dashboard API"""

    def __init__(self):
        self.base_url = f"http://{FRPS_DASHBOARD_HOST}:{FRPS_DASHBOARD_PORT}"
        self.auth = HTTPBasicAuth(FRPS_DASHBOARD_USER, FRPS_DASHBOARD_PASS)
        self.timeout = 5

    def _request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make a request to the frps API"""
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                auth=self.auth,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            logger.warning(f"Could not connect to frps dashboard at {self.base_url}")
            return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout connecting to frps dashboard")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error from frps dashboard: {e}")
            return None
        except Exception as e:
            logger.error(f"Error querying frps API: {e}")
            return None

    def get_server_info(self) -> Optional[Dict[str, Any]]:
        """
        Get server-wide statistics.

        Returns dict with:
        - version: frps version
        - bindPort, vhostHTTPPort, vhostHTTPSPort: port config
        - totalTrafficIn, totalTrafficOut: total bytes
        - curConns: current connections
        - clientCounts: number of connected clients
        - proxyTypeCounts: dict of proxy type -> count
        """
        return self._request("/api/serverinfo")

    def get_proxies_by_type(self, proxy_type: str) -> List[Dict[str, Any]]:
        """
        Get all proxies of a specific type.

        Args:
            proxy_type: 'http', 'https', 'tcp', 'udp', 'stcp', 'xtcp'

        Returns list of proxy info dicts with:
        - name: proxy name
        - conf: configuration
        - todayTrafficIn, todayTrafficOut: bytes today
        - curConns: current connections
        - lastStartTime, lastCloseTime: timestamps
        - status: 'online' or 'offline'
        """
        data = self._request(f"/api/proxy/{proxy_type}")
        if data and "proxies" in data:
            return data["proxies"] or []
        return []

    def get_proxy_detail(self, proxy_type: str, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a specific proxy"""
        return self._request(f"/api/proxy/{proxy_type}/{name}")

    def get_proxy_traffic(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get 7-day traffic history for a specific proxy.

        Returns dict with:
        - name: proxy name
        - trafficIn: list of 7 daily values (bytes)
        - trafficOut: list of 7 daily values (bytes)
        """
        return self._request(f"/api/traffic/{name}")

    def get_all_proxy_stats(self) -> Dict[str, List[Dict]]:
        """
        Get stats for all proxy types.

        Returns dict keyed by proxy type with list of proxy stats.
        """
        result = {}
        for proxy_type in ["http", "https", "tcp"]:
            proxies = self.get_proxies_by_type(proxy_type)
            if proxies:
                result[proxy_type] = proxies
        return result

    def is_available(self) -> bool:
        """Check if frps dashboard is reachable"""
        info = self.get_server_info()
        return info is not None


# Singleton instance for convenience
_client: Optional[FrpsApiClient] = None


def get_frps_client() -> FrpsApiClient:
    """Get or create the frps API client singleton"""
    global _client
    if _client is None:
        _client = FrpsApiClient()
    return _client
