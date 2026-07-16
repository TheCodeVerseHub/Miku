"""
Shared database module for the dashboard backend.

Extracts the connection pool into its own module so both main.py
and health.py can import it without circular import errors.
"""

import logging
from typing import Optional

import asyncpg

from .config import config

logger = logging.getLogger("dashboard.db")

_pool: Optional[asyncpg.Pool] = None


async def get_db() -> asyncpg.Pool:
    """Get or create the database connection pool (singleton)."""
    global _pool
    if _pool is None:
        if not config.database_url:
            raise RuntimeError("DATABASE_URL not configured")
        _pool = await asyncpg.create_pool(
            config.database_url,
            min_size=1,
            max_size=5,
            command_timeout=30,
            statement_cache_size=0,
            max_inactive_connection_lifetime=1800.0,
        )
        logger.info("Database connection pool created")
    return _pool


async def close_db() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")
