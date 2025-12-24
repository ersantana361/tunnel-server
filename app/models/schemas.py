"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    max_tunnels: int = 10


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    max_tunnels: Optional[int] = None


class TunnelCreate(BaseModel):
    name: str
    type: str  # http, https, tcp
    local_port: int
    local_host: str = "127.0.0.1"
    subdomain: Optional[str] = None  # for http/https
    remote_port: Optional[int] = None  # for tcp


class TunnelStatusUpdate(BaseModel):
    is_active: bool


class TunnelUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    local_port: Optional[int] = None
    local_host: Optional[str] = None
    subdomain: Optional[str] = None
    remote_port: Optional[int] = None
