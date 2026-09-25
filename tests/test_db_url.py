"""Tests for `DATABASE_URL` DSN normalisation (`shared/db_url.py`).

Regression: `DATABASE_URL` was documented as `postgresql+asyncpg://…` in
`.env.example`, `docker-compose.yml`, the README and CI, but that is a
*SQLAlchemy* URL. Passed straight to `asyncpg.create_pool` it raises
`ValueError: invalid URI scheme: postgresql+asyncpg`, so the bot and the
dashboard died at startup on the configuration the docs told people to write.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from shared.db_url import to_async_sqlalchemy_url, to_asyncpg_dsn

# The four spellings the repo actually ships/uses.
DOCUMENTED = "postgresql+asyncpg://user:password@localhost:5432/miku"
COMPOSE = "postgresql+asyncpg://miku:miku_secret@postgres:5432/miku"
PLAIN = "postgresql://user:password@localhost:5432/miku"
HEROKU = "postgres://user:password@localhost:5432/miku"


class TestToAsyncpgDsn:
    @pytest.mark.parametrize("url", [DOCUMENTED, COMPOSE, PLAIN, HEROKU])
    def test_no_driver_suffix_remains(self, url):
        dsn = to_asyncpg_dsn(url)
        assert dsn.startswith("postgresql://")
        assert "+" not in dsn.split("://", 1)[0]

    def test_credentials_and_query_are_preserved(self):
        url = "postgresql+asyncpg://u:p%40ss@db.example.com:6432/miku?sslmode=require"
        assert to_asyncpg_dsn(url) == (
            "postgresql://u:p%40ss@db.example.com:6432/miku?sslmode=require"
        )

    @pytest.mark.parametrize("url", ["", "not-a-url", "postgresql://"])
    def test_malformed_input_is_returned_untouched(self, url):
        assert to_asyncpg_dsn(url) == url


class TestToAsyncSqlalchemyUrl:
    @pytest.mark.parametrize("url", [PLAIN, HEROKU])
    def test_asyncpg_driver_is_added(self, url):
        assert to_async_sqlalchemy_url(url) == DOCUMENTED

    def test_sync_driver_is_replaced(self):
        assert to_async_sqlalchemy_url("postgresql+psycopg2://u:p@db/miku") == (
            "postgresql+asyncpg://u:p@db/miku"
        )

    def test_already_correct_url_is_stable(self):
        assert to_async_sqlalchemy_url(DOCUMENTED) == DOCUMENTED


class TestConsumersUseTheHelper:
    """The helper only helps if the pool-creating code actually calls it."""

    @pytest.mark.asyncio
    async def test_bot_pool_strips_the_sqlalchemy_driver(self):
        from utils import database as db

        with (
            patch.dict(os.environ, {"DATABASE_URL": DOCUMENTED}),
            patch("asyncpg.create_pool", AsyncMock(return_value=AsyncMock())) as create_pool,
        ):
            original = db._pool
            db._pool = None
            try:
                await db.get_pool()
            finally:
                db._pool = original

        assert create_pool.await_args.args[0] == PLAIN

    @pytest.mark.asyncio
    async def test_dashboard_pool_strips_the_sqlalchemy_driver(self):
        from dashboard.backend import database as db

        with (
            patch.object(db.config, "database_url", DOCUMENTED),
            patch("asyncpg.create_pool", AsyncMock(return_value=AsyncMock())) as create_pool,
        ):
            original = db._pool
            db._pool = None
            try:
                await db.get_db()
            finally:
                db._pool = original

        assert create_pool.await_args.args[0] == PLAIN
