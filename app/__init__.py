"""
Tunnel Server - Admin Dashboard & User Management
FastAPI application factory
"""
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from .database import init_db
from .routes import auth, users, tunnels, stats


def get_dashboard_html() -> str:
    """Load dashboard HTML template"""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    with open(template_path, "r") as f:
        return f.read()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize database on startup"""
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="Tunnel Server Admin",
        description="Admin dashboard for managing tunnel server users and tunnels",
        version="1.0.0",
        lifespan=lifespan
    )

    # Register routers
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(tunnels.router, prefix="/api/tunnels", tags=["tunnels"])
    app.include_router(stats.router, prefix="/api", tags=["stats"])

    # Serve dashboard at root
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve admin dashboard"""
        return get_dashboard_html()

    return app
