"""
Authentication endpoint tests
"""
import pytest


def test_login_invalid_credentials(client):
    """Test login with invalid credentials returns 401"""
    response = client.post(
        "/api/auth/login",
        json={"email": "invalid@test.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_missing_fields(client):
    """Test login with missing fields returns 422"""
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 422


def test_protected_endpoint_without_auth(client):
    """Test protected endpoint without auth returns 403"""
    response = client.get("/api/users")
    assert response.status_code == 403


def test_protected_endpoint_with_invalid_token(client):
    """Test protected endpoint with invalid token returns 401"""
    response = client.get(
        "/api/users",
        headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401


def test_dashboard_loads(client):
    """Test dashboard HTML loads successfully"""
    response = client.get("/")
    assert response.status_code == 200
    assert "Tunnel Server" in response.text
