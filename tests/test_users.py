"""
User management endpoint tests
"""
import pytest


def test_list_users_requires_admin(client):
    """Test listing users requires admin authentication"""
    response = client.get("/api/users")
    assert response.status_code == 403


def test_create_user_requires_admin(client):
    """Test creating user requires admin authentication"""
    response = client.post(
        "/api/users",
        json={
            "email": "test@example.com",
            "password": "testpassword",
            "max_tunnels": 5
        }
    )
    assert response.status_code == 403


def test_update_user_requires_admin(client):
    """Test updating user requires admin authentication"""
    response = client.put(
        "/api/users/1",
        json={"is_active": False}
    )
    assert response.status_code == 403


def test_delete_user_requires_admin(client):
    """Test deleting user requires admin authentication"""
    response = client.delete("/api/users/1")
    assert response.status_code == 403


def test_regenerate_token_requires_admin(client):
    """Test regenerating token requires admin authentication"""
    response = client.post("/api/users/1/regenerate-token")
    assert response.status_code == 403
