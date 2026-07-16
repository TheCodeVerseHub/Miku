"""
Health check endpoints for the Miku Dashboard and Bot.

Provides:
- /health — Basic health check (used by Docker healthcheck)
- /health/db — Database connectivity check
- /health/ready — Readiness probe (checks DB + Discord API)
"""

import logging
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter

logger = logging.getLogger("dashboard.health")

router = APIRouter(prefix="/health", tags=["health"])

START_TIME = time.time()


def _uptime() -> str:
    """Return human-readable uptime."""
    seconds = int(time.time() - START_TIME)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


@router.get("")
async def health():
    """Basic health check — always responds unless the process is dying."""
    return {
        "status": "ok",
        "service": "miku-dashboard",
        "version": os.getenv("MIKU_VERSION", "0.1.0"),
        "uptime": _uptime(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db")
async def health_db():
    """Database connectivity check."""
    from .database import get_db

    db = None
    try:
        db = await get_db()
        async with db.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "ok",
            "database": "connected",
        }
    except Exception as e:
        logger.error("Health check DB failure: %s", e)
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e),
        }


@router.get("/ready")
async def health_ready():
    """Readiness probe — confirms DB is reachable and bot events are being processed.

    Returns HTTP 503 if not healthy (handled by FastAPI exception handling).
    """
    db_status = await health_db()
    if db_status.get("status") != "ok":
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": db_status.get("database", "unknown"),
                "uptime": _uptime(),
            },
        )

    return {
        "status": "ready",
        "service": "miku-dashboard",
        "uptime": _uptime(),
        "database": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
