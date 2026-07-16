"""
Alembic configuration for Miku.

Uses the async SQLAlchemy engine pattern from the bot's legacy codebase,
adapted for Alembic's async migration runner.

Usage:
    alembic revision --autogenerate -m "add_voice_xp_table"
    alembic upgrade head
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import our declarative Base and all models so autogenerate can detect them
# (This imports from the legacy bot/ codebase which uses SQLAlchemy)
from bot.extensions.leveling.models.sql import Base as LegacyBase

target_metadata = LegacyBase.metadata

# Override sqlalchemy.url from environment if set
DATABASE_URL = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Set it in your .env or in alembic.ini"
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() here emit the given SQL to a script.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run migrations with a connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode using create_async_engine."""
    # Use asyncpg driver for the URL
    async_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    if "+asyncpg" not in async_url:
        # Already has a driver specifier
        parts = async_url.split("://", 1)
        if "+" not in parts[0]:
            async_url = f"{parts[0]}+asyncpg://{parts[1]}"

    connectable = create_async_engine(async_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
