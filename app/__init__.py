"""
Tunnel Server - Admin Dashboard & User Management
FastAPI application factory
"""
import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from .database import init_db
from .routes import auth, users, tunnels, stats, ssh_keys
from .services.dns import setup_tunnel_dns
from .services.metrics import collect_tunnel_metrics, cleanup_old_metrics

logger = logging.getLogger(__name__)


def get_dashboard_html() -> str:
    """Load dashboard HTML template"""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    with open(template_path, "r") as f:
        return f.read()


async def collect_metrics_periodically():
    """Background task to collect frps metrics every 60 seconds"""
    while True:
        try:
            collect_tunnel_metrics()
        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")
        await asyncio.sleep(60)


async def cleanup_metrics_periodically():
    """Background task to clean up old metrics daily"""
    while True:
        await asyncio.sleep(86400)  # 24 hours
        try:
            cleanup_old_metrics(days=7)
        except Exception as e:
            logger.error(f"Metrics cleanup failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize database, DNS, and background tasks"""
    init_db()
    setup_tunnel_dns()

    # Start background tasks
    collect_task = asyncio.create_task(collect_metrics_periodically())
    cleanup_task = asyncio.create_task(cleanup_metrics_periodically())

    yield

    # Cancel background tasks on shutdown
    collect_task.cancel()
    cleanup_task.cancel()
    try:
        await collect_task
    except asyncio.CancelledError:
        pass
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


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
    app.include_router(ssh_keys.router, prefix="/api/ssh-keys", tags=["ssh-keys"])

    # Serve dashboard at root
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve admin dashboard"""
        return get_dashboard_html()

    return app
