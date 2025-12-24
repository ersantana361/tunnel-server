# API Reference

Complete documentation for all API endpoints provided by the Tunnel Server admin dashboard.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Authentication](#authentication-endpoints)
  - [Users](#user-endpoints)
  - [Tunnels](#tunnel-endpoints)
  - [Statistics](#statistics-endpoints)
  - [Activity](#activity-endpoints)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

---

## Overview

### Base URL

```
Development: http://localhost:8000
Production:  http://your-server:8000
```

### Content Type

All API requests and responses use JSON:

```
Content-Type: application/json
```

### API Versioning

Currently, all endpoints are unversioned and available at `/api/*`. Future versions may introduce `/api/v2/*` paths.

---

## Authentication

### JWT Bearer Token

Most API endpoints require authentication using a JWT bearer token.

**Header Format:**
```
Authorization: Bearer <jwt_token>
```

**Token Acquisition:**
Obtain a token by calling the login endpoint with valid credentials.

**Token Lifetime:**
- Default: 30 minutes
- Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` in code

### Permission Levels

| Level | Description | Endpoints |
|-------|-------------|-----------|
| Public | No authentication required | `GET /`, `POST /api/auth/login` |
| Authenticated | Valid JWT required | `GET /api/tunnels` |
| Admin | JWT + is_admin=1 required | All `/api/users/*`, `/api/stats`, `/api/activity` |

---

## Endpoints

### Authentication Endpoints

#### POST /api/auth/login

Authenticate a user and receive a JWT token.

**Request:**
```json
{
  "email": "admin@localhost",
  "password": "your-password"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "admin@localhost",
    "is_admin": true,
    "tunnel_token": "745d5d29f549f9e16cc8d88c9dede02e..."
  }
}
```

**Error Responses:**

| Status | Message | Cause |
|--------|---------|-------|
| 401 | Invalid credentials | Wrong email or password |
| 401 | Account disabled | User's is_active = 0 |

**Example:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@localhost","password":"your-password"}'
```

---

### User Endpoints

#### GET /api/users

List all users (admin only).

**Headers:**
```
Authorization: Bearer <admin_jwt_token>
```

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": 1,
      "email": "admin@localhost",
      "token": "745d5d29f549f9e16cc8d88c9dede02e...",
      "is_admin": 1,
      "is_active": 1,
      "max_tunnels": 999,
      "created_at": "2024-01-15 10:30:00",
      "last_login": "2024-01-15 14:22:33",
      "active_tunnels": 2
    },
    {
      "id": 2,
      "email": "developer@example.com",
      "token": "abc123def456...",
      "is_admin": 0,
      "is_active": 1,
      "max_tunnels": 10,
      "created_at": "2024-01-15 11:00:00",
      "last_login": null,
      "active_tunnels": 0
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/api/users \
  -H "Authorization: Bearer <token>"
```

---

#### POST /api/users

Create a new user (admin only).

**Headers:**
```
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "secure-password-123",
  "max_tunnels": 10
}
```

**Field Validation:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| email | string | Yes | Valid email format |
| password | string | Yes | Any length (hashed with bcrypt) |
| max_tunnels | integer | No | Default: 10 |

**Response (200 OK):**
```json
{
  "id": 3,
  "email": "newuser@example.com",
  "tunnel_token": "new-64-char-hex-token...",
  "max_tunnels": 10
}
```

**Error Responses:**

| Status | Message | Cause |
|--------|---------|-------|
| 400 | Email already exists | Duplicate email |
| 403 | Admin access required | Non-admin JWT |
| 422 | Validation error | Invalid email format |

**Example:**
```bash
curl -X POST http://localhost:8000/api/users \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email":"new@example.com","password":"pass123","max_tunnels":5}'
```

---

#### PUT /api/users/{user_id}

Update a user's settings (admin only).

**Headers:**
```
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| user_id | integer | Target user's ID |

**Request:**
```json
{
  "is_active": false,
  "max_tunnels": 20
}
```

**Field Validation:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| is_active | boolean | No | Enable/disable account |
| max_tunnels | integer | No | Update tunnel limit |

**Response (200 OK):**
```json
{
  "message": "User updated successfully"
}
```

**Example:**
```bash
# Disable a user
curl -X PUT http://localhost:8000/api/users/2 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Update tunnel limit
curl -X PUT http://localhost:8000/api/users/2 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"max_tunnels": 25}'
```

---

#### DELETE /api/users/{user_id}

Delete a user and their tunnels (admin only).

**Headers:**
```
Authorization: Bearer <admin_jwt_token>
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| user_id | integer | Target user's ID |

**Response (200 OK):**
```json
{
  "message": "User deleted successfully"
}
```

**Error Responses:**

| Status | Message | Cause |
|--------|---------|-------|
| 400 | Cannot delete admin or user not found | Attempted to delete admin or invalid ID |

**Cascade Behavior:**
- All tunnels owned by the user are deleted first
- Activity logs referencing the user remain (user_id becomes orphaned)

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/users/2 \
  -H "Authorization: Bearer <token>"
```

---

#### POST /api/users/{user_id}/regenerate-token

Regenerate a user's tunnel token (admin only).

**Headers:**
```
Authorization: Bearer <admin_jwt_token>
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| user_id | integer | Target user's ID |

**Response (200 OK):**
```json
{
  "token": "new-64-character-hex-token..."
}
```

**Side Effects:**
- Old token immediately becomes invalid
- Any connected tunnels using old token will disconnect
- User must update their client configuration

**Example:**
```bash
curl -X POST http://localhost:8000/api/users/2/regenerate-token \
  -H "Authorization: Bearer <token>"
```

---

### Tunnel Endpoints

#### GET /api/tunnels

List tunnels. Admins see all tunnels; regular users see only their own.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response (200 OK):**
```json
{
  "tunnels": [
    {
      "id": 1,
      "user_id": 2,
      "user_email": "developer@example.com",
      "name": "api-server",
      "type": "http",
      "subdomain": "api",
      "remote_port": null,
      "is_active": 1,
      "created_at": "2024-01-15 12:00:00",
      "last_connected": "2024-01-15 14:30:00"
    },
    {
      "id": 2,
      "user_id": 2,
      "user_email": "developer@example.com",
      "name": "postgres-dev",
      "type": "tcp",
      "subdomain": null,
      "remote_port": 5432,
      "is_active": 0,
      "created_at": "2024-01-15 12:05:00",
      "last_connected": null
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Tunnel ID |
| user_id | integer | Owner user ID |
| user_email | string | Owner email (admin view only) |
| name | string | Tunnel name |
| type | string | "http", "https", or "tcp" |
| subdomain | string | Subdomain for HTTP/HTTPS tunnels |
| remote_port | integer | Port for TCP tunnels |
| is_active | integer | 1 = connected, 0 = offline |
| created_at | string | Creation timestamp |
| last_connected | string | Last connection timestamp |

**Example:**
```bash
curl http://localhost:8000/api/tunnels \
  -H "Authorization: Bearer <token>"
```

---

### Statistics Endpoints

#### GET /api/stats

Get server statistics (admin only).

**Headers:**
```
Authorization: Bearer <admin_jwt_token>
```

**Response (200 OK):**
```json
{
  "users": {
    "total": 5,
    "active": 4
  },
  "tunnels": {
    "total": 12,
    "active": 3
  },
  "recent_activity": [
    {
      "id": 100,
      "user_id": 1,
      "action": "login",
      "details": "User admin@localhost logged in",
      "ip_address": "192.168.1.100",
      "created_at": "2024-01-15 14:22:33",
      "email": "admin@localhost"
    }
  ]
}
```

**Response Fields:**

| Field | Description |
|-------|-------------|
| users.total | Total non-admin users |
| users.active | Users with is_active=1 |
| tunnels.total | Total tunnels configured |
| tunnels.active | Currently connected tunnels |
| recent_activity | Last 10 activity log entries |

**Example:**
```bash
curl http://localhost:8000/api/stats \
  -H "Authorization: Bearer <token>"
```

---

### Activity Endpoints

#### GET /api/activity

Get activity logs (admin only).

**Headers:**
```
Authorization: Bearer <admin_jwt_token>
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | integer | 50 | Maximum entries to return |

**Response (200 OK):**
```json
{
  "logs": [
    {
      "id": 100,
      "user_id": 1,
      "action": "login",
      "details": "User admin@localhost logged in",
      "ip_address": "192.168.1.100",
      "created_at": "2024-01-15 14:22:33",
      "email": "admin@localhost"
    },
    {
      "id": 99,
      "user_id": 1,
      "action": "user_created",
      "details": "Created user developer@example.com",
      "ip_address": "192.168.1.100",
      "created_at": "2024-01-15 14:20:00",
      "email": "admin@localhost"
    }
  ]
}
```

**Action Types:**

| Action | Description |
|--------|-------------|
| login | User logged into dashboard |
| user_created | New user was created |
| user_updated | User settings changed |
| user_deleted | User was deleted |
| token_regenerated | User token was regenerated |

**Example:**
```bash
# Get last 50 activities (default)
curl http://localhost:8000/api/activity \
  -H "Authorization: Bearer <token>"

# Get last 100 activities
curl "http://localhost:8000/api/activity?limit=100" \
  -H "Authorization: Bearer <token>"
```

---

## Error Handling

### Error Response Format

All errors return a JSON object with a `detail` field:

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Invalid input, duplicate email |
| 401 | Unauthorized | Invalid/expired token, wrong credentials |
| 403 | Forbidden | Non-admin accessing admin endpoint |
| 404 | Not Found | Resource doesn't exist |
| 422 | Validation Error | Invalid request body format |
| 500 | Server Error | Unexpected server-side error |

### Validation Errors (422)

Pydantic validation errors include detailed information:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting

Currently, no rate limiting is implemented. For production deployments, consider adding:

1. **Nginx rate limiting** (recommended)
2. **FastAPI middleware** (application level)
3. **Fail2ban** for login attempts

### Recommended Limits

| Endpoint | Suggested Limit |
|----------|-----------------|
| POST /api/auth/login | 5 requests/minute per IP |
| POST /api/users | 10 requests/minute per admin |
| GET /api/* | 100 requests/minute per user |

---

## Code Examples

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# Login
response = requests.post(f"{BASE_URL}/api/auth/login", json={
    "email": "admin@localhost",
    "password": "your-password"
})
token = response.json()["access_token"]

# Create user
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{BASE_URL}/api/users",
    headers=headers,
    json={
        "email": "new@example.com",
        "password": "password123",
        "max_tunnels": 10
    }
)
print(response.json())
```

### JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8000';

// Login
const loginResponse = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        email: 'admin@localhost',
        password: 'your-password'
    })
});
const { access_token } = await loginResponse.json();

// Get users
const usersResponse = await fetch(`${BASE_URL}/api/users`, {
    headers: { 'Authorization': `Bearer ${access_token}` }
});
const { users } = await usersResponse.json();
console.log(users);
```

### cURL

```bash
# Store token in variable
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@localhost","password":"pass"}' \
  | jq -r '.access_token')

# Use token in subsequent requests
curl http://localhost:8000/api/users \
  -H "Authorization: Bearer $TOKEN"
```

---

## Related Documentation

- [Architecture](../architecture/README.md) - System design
- [Security](../security/README.md) - Authentication details
- [Database](../database/README.md) - Schema reference
