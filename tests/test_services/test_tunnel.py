"""
Tunnel service unit tests
"""
import pytest
from app.services.tunnel import (
    get_public_url,
    generate_frpc_config,
)
from app.models.schemas import TunnelCreate


def test_get_public_url_http():
    """Test HTTP tunnel public URL generation"""
    url = get_public_url("http", subdomain="myapp", domain="example.com")
    assert url == "http://myapp.example.com"


def test_get_public_url_https():
    """Test HTTPS tunnel public URL generation"""
    url = get_public_url("https", subdomain="secure", domain="example.com")
    assert url == "https://secure.example.com"


def test_get_public_url_tcp():
    """Test TCP tunnel public URL generation"""
    url = get_public_url("tcp", remote_port=8080, domain="example.com")
    assert url == "tcp://example.com:8080"


def test_get_public_url_http_no_subdomain():
    """Test HTTP URL without subdomain"""
    url = get_public_url("http", domain="example.com")
    assert url == "http://example.com"


def test_generate_frpc_config_http():
    """Test frpc config generation for HTTP tunnel"""
    tunnel = TunnelCreate(
        name="web",
        type="http",
        local_port=3000,
        local_host="127.0.0.1",
        subdomain="myapp"
    )
    config = generate_frpc_config(tunnel, "example.com")

    assert "[web]" in config
    assert "type = http" in config
    assert "local_port = 3000" in config
    assert "subdomain = myapp" in config


def test_generate_frpc_config_tcp():
    """Test frpc config generation for TCP tunnel"""
    tunnel = TunnelCreate(
        name="ssh",
        type="tcp",
        local_port=22,
        local_host="127.0.0.1",
        remote_port=2222
    )
    config = generate_frpc_config(tunnel, "example.com")

    assert "[ssh]" in config
    assert "type = tcp" in config
    assert "local_port = 22" in config
    assert "remote_port = 2222" in config


def test_generate_frpc_config_with_common():
    """Test frpc config generation with common section"""
    tunnel = TunnelCreate(
        name="web",
        type="http",
        local_port=3000,
        subdomain="myapp"
    )
    config = generate_frpc_config(
        tunnel,
        "example.com",
        include_common=True,
        user_token="my-secret-token"
    )

    assert "[common]" in config
    assert "server_addr = example.com" in config
    assert "server_port = 7000" in config
    assert "token = my-secret-token" in config
