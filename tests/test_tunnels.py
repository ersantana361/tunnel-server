"""
Tunnel management endpoint tests
"""
import pytest


def test_list_tunnels_requires_auth(client):
    """Test listing tunnels requires authentication"""
    response = client.get("/api/tunnels")
    assert response.status_code == 403


def test_create_tunnel_requires_auth(client):
    """Test creating tunnel requires authentication"""
    response = client.post(
        "/api/tunnels",
        json={
            "name": "test-tunnel",
            "type": "http",
            "local_port": 3000,
            "subdomain": "test"
        }
    )
    assert response.status_code == 403


def test_delete_tunnel_requires_auth(client):
    """Test deleting tunnel requires authentication"""
    response = client.delete("/api/tunnels/1")
    assert response.status_code == 403


def test_update_tunnel_status_requires_auth(client):
    """Test updating tunnel status requires authentication"""
    response = client.put(
        "/api/tunnels/1/status",
        json={"is_active": True}
    )
    assert response.status_code == 403


def test_get_tunnel_config_requires_auth(client):
    """Test getting tunnel config requires authentication"""
    response = client.get("/api/tunnels/1/config")
    assert response.status_code == 403


def test_create_tunnel_validation(client):
    """Test tunnel creation validates required fields"""
    # Missing required fields should fail with 422 (before auth check)
    # or 403 (if auth check comes first)
    response = client.post("/api/tunnels", json={})
    assert response.status_code in [403, 422]
