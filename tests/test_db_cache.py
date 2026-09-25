"""Tests for the in-memory leveling cache (`utils/db_cache.py`).

This module had no coverage at all despite owning the XP hot path, the batched
flush and the failure/backoff behaviour, so it is where silent XP loss hides.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.level_service import LevelService
from utils.db_cache import LevelingCache

GUILD_ID = 987654321098765432
USER_ID = 123456789012345678


class _AsyncCM:
    """Minimal async context manager, standing in for `pool.acquire()`."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc_info):
        return False


@pytest.fixture
def bot() -> MagicMock:
    """A bot mock good enough for a cache that is constructed but never started."""
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    bot.is_closed = MagicMock(return_value=False)
    return bot


@pytest.fixture
def cache(bot) -> LevelingCache:
    return LevelingCache(bot, flush_interval=30)


@pytest.fixture
def fake_pool():
    """A pool mock whose `acquire()` yields a connection with batch methods."""
    conn = MagicMock()
    conn.executemany = AsyncMock()

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCM(conn))
    return pool, conn


class TestUserWritePath:
    """`update_user_xp` is on the message hot path; it must never raise."""

    @pytest.mark.asyncio
    async def test_message_xp_reaches_the_cache(self, bot, mock_discord_message):
        """Regression: every XP write raised TypeError, so no XP was ever awarded.

        `_get_user_lock` was an ``async def`` used as an async context manager,
        which raises before any state is written.
        """
        cache = LevelingCache(bot)
        service = LevelService(bot, cache=cache)

        with (
            patch("utils.database.get_user_data", AsyncMock(return_value=None)),
            patch("utils.database.get_guild_settings", AsyncMock(return_value=None)),
        ):
            result = await service.award_message_xp(mock_discord_message)

        assert result is not None, "the message should have been awarded XP"
        data = await cache.get_user_data(USER_ID, GUILD_ID)
        assert data is not None
        assert data["xp"] == result["xp_gained"]
        assert data["messages"] == 1

    @pytest.mark.asyncio
    async def test_update_user_xp_creates_and_updates_entries(self, cache):
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)
        await cache.update_user_xp(USER_ID, GUILD_ID, 45, 0, 2, 1_060.0)

        data = await cache.get_user_data(USER_ID, GUILD_ID)
        assert data is not None
        assert data["xp"] == 45
        assert data["messages"] == 2
        assert data["last_message_time"] == 1_060.0

    @pytest.mark.asyncio
    async def test_user_locks_are_shared_per_user(self, cache):
        assert cache._get_user_lock(1, 2) is cache._get_user_lock(1, 2)
        assert cache._get_user_lock(1, 2) is not cache._get_user_lock(1, 3)


class TestFlush:
    """Dirty entries are persisted in batches, then marked clean."""

    @pytest.mark.asyncio
    async def test_flush_persists_dirty_users_in_one_batch(self, cache, fake_pool):
        pool, conn = fake_pool
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)

        with patch("utils.database.get_pool", AsyncMock(return_value=pool)):
            await cache.flush_all()

        conn.executemany.assert_awaited_once()
        sql, records = conn.executemany.await_args.args
        assert "INSERT INTO user_levels" in sql
        assert records == [(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)]
        assert cache.get_metrics()["db_user_writes"] == 1

    @pytest.mark.asyncio
    async def test_clean_entries_are_not_written_again(self, cache, fake_pool):
        pool, conn = fake_pool
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)

        with patch("utils.database.get_pool", AsyncMock(return_value=pool)):
            await cache.flush_all()
            await cache.flush_all()

        assert conn.executemany.await_count == 1, "a clean entry must not be re-flushed"

    @pytest.mark.asyncio
    async def test_failed_flush_keeps_entries_dirty_for_retry(self, cache, fake_pool):
        pool, conn = fake_pool
        conn.executemany = AsyncMock(side_effect=RuntimeError("database is down"))
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)

        with patch("utils.database.get_pool", AsyncMock(return_value=pool)):
            await cache.flush_all()  # must not raise
            assert cache.get_metrics()["db_errors"] == 1

            conn.executemany = AsyncMock()
            await cache.flush_all()

        conn.executemany.assert_awaited_once()
