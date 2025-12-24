"""
Pytest fixtures for Tunnel Server tests
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Set test database before importing app
_test_db_file = None


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables"""
    global _test_db_file
    # Create temp file for test database
    fd, _test_db_file = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.environ['DB_PATH'] = _test_db_file
    os.environ['JWT_SECRET'] = 'test-secret-key-for-testing'

    yield

    # Cleanup
    if os.path.exists(_test_db_file):
        os.unlink(_test_db_file)


@pytest.fixture
def client(setup_test_env):
    """Create test client with fresh database"""
    from app import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin_token(client):
    """Get admin JWT token for authenticated requests"""
    # First, we need to get admin credentials from logs or create them
    # For testing, we'll read from DB directly
    import sqlite3
    from app.config import DB_FILE

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE is_admin = 1")
    admin = cursor.fetchone()
    conn.close()

    if not admin:
        pytest.skip("No admin user found")

    # Login with a known password (for tests, we'd need to set this up)
    # This is a placeholder - real tests would need proper test data setup
    return None


@pytest.fixture
def auth_headers(admin_token):
    """Get authorization headers for API calls"""
    if admin_token is None:
        pytest.skip("No admin token available")
    return {"Authorization": f"Bearer {admin_token}"}
