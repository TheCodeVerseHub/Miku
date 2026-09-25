"""
Health check endpoints for the Miku Dashboard and Bot.

Provides:
- /health — Basic health check (used by Docker healthcheck)
- /health/db — Database connectivity check
- /health/ready — Readiness probe (checks DB + Discord API)

These routes are deliberately unauthenticated (a container healthcheck cannot
hold a session), so they must never echo anything about the deployment back to
the caller: failures return a generic reason and the real error goes to the log.
"""

import logging
import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger("dashboard.health")

router = APIRouter(prefix="/health", tags=["health"])

START_TIME = time.time()

#: Public failure text. Deliberately says nothing about host/credentials.
DB_UNAVAILABLE = "database unavailable"


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


async def probe_database() -> tuple[bool, str | None]:
    """Run `SELECT 1` and report whether the database is reachable.

    Returns ``(ok, public_reason)``. The exception's *type* is reported because
    "connection refused" and "password authentication failed" are genuinely
    useful to an operator, while its message (which can contain the DSN, host,
    port and role) is only logged - these routes are public.
    """
    from .database import get_db

    try:
        db = await get_db()
        async with db.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as exc:
        # `logger.exception` keeps the full traceback in the server log.
        logger.exception("Health check DB failure")
        return False, f"{DB_UNAVAILABLE} ({type(exc).__name__})"
    return True, None


@router.get("")
async def health():
    """Basic health check — always responds unless the process is dying."""
    return {
        "status": "ok",
        "service": "miku-dashboard",
        "version": os.getenv("MIKU_VERSION", "0.1.0"),
        "uptime": _uptime(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/db")
async def health_db():
    """Database connectivity check.

    Returns 503 (not 200) when the database is down, so a plain HTTP status
    check in a load balancer or monitor does the right thing.
    """
    ok, reason = await probe_database()
    if not ok:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected", "reason": reason},
        )
    return {
        "status": "ok",
        "database": "connected",
    }


@router.get("/ready")
async def health_ready():
    """Readiness probe — confirms DB is reachable and bot events are being processed.

    Returns HTTP 503 if not healthy.
    """
    ok, _reason = await probe_database()
    if not ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "uptime": _uptime(),
            },
        )

    return {
        "status": "ready",
        "service": "miku-dashboard",
        "uptime": _uptime(),
        "database": "connected",
        "timestamp": datetime.now(UTC).isoformat(),
    }
