# Architecture

This document provides a comprehensive overview of the Tunnel Server architecture, including system components, data flow, and design decisions.

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Application Structure](#application-structure)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Design Decisions](#design-decisions)

---

## System Overview

The Tunnel Server is part of a larger self-hosted tunnel service that consists of two main components:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION SERVER                             │
│                                                                  │
│  ┌────────────────────────┐    ┌────────────────────────────┐  │
│  │   Admin Dashboard      │    │     frp Server (frps)      │  │
│  │   (This Application)   │    │                            │  │
│  │                        │    │   - Handles tunnel traffic │  │
│  │   Port: 8000           │    │   - Port: 7000 (control)   │  │
│  │                        │    │   - Port: 80 (HTTP)        │  │
│  │   - User Management    │    │   - Port: 443 (HTTPS)      │  │
│  │   - Authentication     │    │                            │  │
│  │   - Monitoring         │    │                            │  │
│  │   - Activity Logging   │    │                            │  │
│  └───────────┬────────────┘    └─────────────┬──────────────┘  │
│              │                               │                   │
│              └───────────┬───────────────────┘                  │
│                          │                                       │
│                    ┌─────▼─────┐                                │
│                    │  SQLite   │                                │
│                    │  Database │                                │
│                    └───────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ Token-based Authentication
                               │
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT MACHINE                              │
│                                                                  │
│  ┌────────────────────────┐    ┌────────────────────────────┐  │
│  │   Client Dashboard     │    │     frp Client (frpc)      │  │
│  │   Port: 3000           │    │                            │  │
│  │                        │◄───┤   - Connects to frps       │  │
│  │   - Tunnel Config      │    │   - Forwards local ports   │  │
│  │   - Status Display     │    │   - Auto-reconnect         │  │
│  └────────────────────────┘    └────────────────────────────┘  │
│                                          │                       │
│                                          ▼                       │
│                                 ┌─────────────────┐             │
│                                 │  Local Services │             │
│                                 │  (8080, 3000..) │             │
│                                 └─────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### Admin Dashboard (app/)

The admin dashboard is a **modular FastAPI application** with clear separation of concerns:

```
app/
├── __init__.py              # App factory (create_app)
├── config.py                # Configuration
│   ├── JWT Secret
│   ├── Database Path
│   └── frps Config Path
│
├── database.py              # Database Layer
│   ├── init_db() - Schema creation
│   ├── Table definitions
│   └── Admin user creation
│
├── dependencies.py          # FastAPI Dependencies
│   ├── verify_token()
│   └── verify_admin()
│
├── services/                # Business Logic
│   ├── auth.py              # JWT, password hashing
│   ├── tunnel.py            # Config generation, URLs
│   └── activity.py          # Activity logging
│
├── routes/                  # API Routes
│   ├── auth.py              # POST /api/auth/login
│   ├── users.py             # CRUD /api/users
│   ├── tunnels.py           # CRUD /api/tunnels
│   └── stats.py             # GET /api/stats, /api/activity
│
└── templates/
    └── dashboard.html       # Admin dashboard UI (~820 lines)
```

### Why Modular Architecture?

1. **Maintainability**: Each file has single responsibility
2. **Testability**: Easy to unit test individual components
3. **Scalability**: Add new routes/services without bloating
4. **Collaboration**: Multiple devs can work on different modules
5. **HTML editing**: Edit template in proper HTML file with syntax highlighting

### frp Server Integration

The application integrates with [frp (Fast Reverse Proxy)](https://github.com/fatedier/frp):

| Component | Role | Port |
|-----------|------|------|
| frps | Tunnel server daemon | 7000 |
| frpc | Client connector | - |
| Admin App | User management | 8000 |

**Note**: The admin app and frps are separate processes. The admin app manages users and tokens, while frps handles actual tunnel connections.

---

## Application Structure

### Request Flow

```
Client Request
      │
      ▼
┌─────────────────┐
│   Uvicorn       │  ASGI Server
│   (Port 8000)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   FastAPI       │  Web Framework
│   Router        │
└────────┬────────┘
         │
         ├──────────────────────┐
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   API Routes    │    │   HTML Route    │
│   /api/*        │    │   GET /         │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   Auth Layer    │    │  get_admin_html │
│   JWT Verify    │    │  (Static HTML)  │
└────────┬────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│   SQLite DB     │
│   (tunnel.db)   │
└─────────────────┘
```

### Authentication Flow

```
┌──────────┐     POST /api/auth/login      ┌──────────┐
│  Client  │ ─────────────────────────────►│  Server  │
│          │     {email, password}          │          │
└──────────┘                               └────┬─────┘
                                                │
                                                ▼
                                    ┌───────────────────┐
                                    │ 1. Lookup user    │
                                    │ 2. Verify bcrypt  │
                                    │ 3. Check active   │
                                    │ 4. Create JWT     │
                                    │ 5. Log activity   │
                                    └─────────┬─────────┘
                                              │
┌──────────┐     {access_token, user}       │
│  Client  │ ◄─────────────────────────────┘
│          │
└──────────┘

Subsequent Requests:
┌──────────┐     Authorization: Bearer <JWT>  ┌──────────┐
│  Client  │ ───────────────────────────────► │  Server  │
└──────────┘                                  └────┬─────┘
                                                   │
                                     ┌─────────────▼─────────────┐
                                     │ verify_token() Dependency │
                                     │ - Decode JWT              │
                                     │ - Check expiration        │
                                     │ - Return user_id          │
                                     └───────────────────────────┘
```

---

## Data Flow

### User Creation Flow

```
Admin Dashboard                    Server                      Database
      │                              │                            │
      │  POST /api/users             │                            │
      │  {email, password, max}      │                            │
      ├─────────────────────────────►│                            │
      │                              │                            │
      │                              │  verify_admin()            │
      │                              ├───────────────────────────►│
      │                              │  Check is_admin = 1        │
      │                              │◄───────────────────────────┤
      │                              │                            │
      │                              │  bcrypt.hashpw(password)   │
      │                              │  secrets.token_hex(32)     │
      │                              │                            │
      │                              │  INSERT INTO users         │
      │                              ├───────────────────────────►│
      │                              │                            │
      │                              │  log_activity()            │
      │                              ├───────────────────────────►│
      │                              │                            │
      │  {id, email, tunnel_token}   │                            │
      │◄─────────────────────────────┤                            │
      │                              │                            │
```

### Tunnel Authentication Flow (with frp)

```
Client App          frp Client        frp Server        Admin App
    │                   │                 │                 │
    │  Configure        │                 │                 │
    │  token + server   │                 │                 │
    ├──────────────────►│                 │                 │
    │                   │                 │                 │
    │                   │  Connect with   │                 │
    │                   │  token          │                 │
    │                   ├────────────────►│                 │
    │                   │                 │                 │
    │                   │                 │  Validate token │
    │                   │                 │  (via config)   │
    │                   │                 │                 │
    │                   │  Connection OK  │                 │
    │                   │◄────────────────┤                 │
    │                   │                 │                 │
    │  Tunnel Active    │                 │                 │
    │◄──────────────────┤                 │                 │
```

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.8+ | Runtime environment |
| FastAPI | 0.109.0 | Web framework |
| Uvicorn | 0.27.0 | ASGI server |
| Pydantic | 2.5.3 | Data validation |
| SQLite | 3.x | Database |

### Security

| Technology | Version | Purpose |
|------------|---------|---------|
| python-jose | 3.3.0 | JWT handling |
| bcrypt | 4.1.2 | Password hashing |
| passlib | 1.7.4 | Password utilities |

### Frontend (Embedded)

| Technology | Purpose |
|------------|---------|
| HTML5 | Structure |
| CSS3 | Styling (dark theme) |
| Vanilla JavaScript | Interactivity |
| Fetch API | HTTP requests |

---

## Design Decisions

### 1. Modular Application Structure

**Decision**: Organize code into multiple files with clear separation of concerns

**Rationale**:
- Each file has single responsibility
- Easy to unit test individual components
- Clear navigation and discoverability
- Supports team collaboration
- CI/CD ready with pytest

**Structure**:
- `app/config.py` - Configuration constants
- `app/database.py` - Database initialization
- `app/services/` - Business logic
- `app/routes/` - API endpoints
- `app/templates/` - HTML templates
- `tests/` - Test suite

### 2. Separate HTML Dashboard

**Decision**: Keep HTML/CSS/JS in a separate template file

**Rationale**:
- Proper syntax highlighting in editors
- Easier to edit frontend code
- Clear separation of concerns
- Can use HTML-specific tooling

**Location**: `app/templates/dashboard.html`

### 3. SQLite Database

**Decision**: Use SQLite instead of PostgreSQL/MySQL

**Rationale**:
- Zero configuration
- No external database server
- File-based (easy backup)
- Sufficient for expected load
- Built into Python

**Trade-offs**:
- Limited concurrent write performance
- No network access (local only)
- Limited to single-server deployments

### 4. JWT Authentication

**Decision**: Use JWT for session management

**Rationale**:
- Stateless authentication
- No server-side session storage
- Easy to validate
- Industry standard

**Trade-offs**:
- Cannot invalidate tokens before expiry
- Token size larger than session ID
- Requires secure secret management

### 5. Token-Based Tunnel Auth

**Decision**: Use 64-character hex tokens for tunnel authentication

**Rationale**:
- Long-lived (unlike JWT)
- Easy to regenerate
- Simple to pass to frp
- Unique per user

**Trade-offs**:
- Must be kept secret
- No built-in expiration
- Requires secure transmission

---

## Scalability Considerations

### Current Limitations

1. **Single Database**: SQLite limits concurrent writes
2. **Single Process**: One uvicorn worker by default
3. **No Caching**: All requests hit the database
4. **Embedded Frontend**: Cannot be served via CDN

### Future Improvements

1. **Database**: Migrate to PostgreSQL for high-traffic
2. **Caching**: Add Redis for session/token caching
3. **Workers**: Run multiple uvicorn workers
4. **Frontend**: Separate frontend for CDN delivery
5. **Load Balancing**: Multiple server instances

---

## Related Documentation

- [API Reference](../api/README.md) - Endpoint details
- [Database Schema](../database/README.md) - Table structures
- [Security](../security/README.md) - Authentication details
- [Deployment](../deployment/README.md) - Production setup
