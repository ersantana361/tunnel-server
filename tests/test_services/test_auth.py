"""
Auth service unit tests
"""
import pytest
from app.services.auth import (
    create_access_token,
    hash_password,
    verify_password,
)


def test_hash_password():
    """Test password hashing"""
    password = "mysecretpassword"
    hashed = hash_password(password)

    assert hashed != password.encode()
    assert len(hashed) > 0


def test_verify_password_correct():
    """Test password verification with correct password"""
    password = "mysecretpassword"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Test password verification with incorrect password"""
    password = "mysecretpassword"
    hashed = hash_password(password)

    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token():
    """Test JWT token creation"""
    data = {"sub": "123"}
    token = create_access_token(data)

    assert isinstance(token, str)
    assert len(token) > 0
    # JWT tokens have 3 parts separated by dots
    assert len(token.split('.')) == 3


def test_create_access_token_different_data():
    """Test that different data produces different tokens"""
    token1 = create_access_token({"sub": "123"})
    token2 = create_access_token({"sub": "456"})

    assert token1 != token2
