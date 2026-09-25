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


class _FakeUserLevels:
    """Tiny stand-in for the `user_levels` table.

    It understands just enough of the two statements the flush issues to model
    the optimistic-concurrency guard: an UPDATE only lands when the row still
    carries the token the caller passed.
    """

    def __init__(self):
        self.rows: dict[tuple[int, int], dict] = {}  # (guild_id, user_id) -> row
        self.executemany = AsyncMock(side_effect=self._executemany)
        self.fetch = AsyncMock(side_effect=self._fetch)
        self.raise_on_write: Exception | None = None

    def seed(self, guild_id: int, user_id: int, *, updated_at, **values):
        self.rows[(guild_id, user_id)] = {
            "guild_id": guild_id,
            "user_id": user_id,
            "updated_at": updated_at,
            **values,
        }

    def acquire(self):
        return _AsyncCM(self)

    async def _executemany(self, sql, records):
        if self.raise_on_write is not None:
            raise self.raise_on_write

        if "INSERT INTO user_levels" in sql:
            for user_id, guild_id, xp, level, messages, last_message_time, stamp in records:
                self.rows.setdefault(
                    (guild_id, user_id),
                    {
                        "guild_id": guild_id,
                        "user_id": user_id,
                        "xp": xp,
                        "level": level,
                        "messages": messages,
                        "last_message_time": last_message_time,
                        "updated_at": stamp,
                    },
                )
            return

        if "UPDATE user_levels" in sql:
            for (
                xp,
                level,
                messages,
                last_message_time,
                user_id,
                guild_id,
                stamp,
                token,
            ) in records:
                row = self.rows.get((guild_id, user_id))
                if row is None or row["updated_at"] != token:
                    continue  # the concurrency guard rejected this write
                row.update(
                    xp=xp,
                    level=level,
                    messages=messages,
                    last_message_time=last_message_time,
                    updated_at=stamp,
                )
            return

        raise AssertionError(f"unexpected statement: {sql}")

    async def _fetch(self, sql, guild_ids, user_ids):
        wanted = set(zip(guild_ids, user_ids, strict=True))
        return [dict(row) for key, row in self.rows.items() if key in wanted]


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
def fake_db() -> _FakeUserLevels:
    return _FakeUserLevels()


@pytest.fixture
def patched_db(fake_db):
    """Route the cache's database calls at the fake table."""
    with patch("utils.database.get_pool", AsyncMock(return_value=fake_db)):
        yield fake_db


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


class TestNewUserSentinel:
    """A member with no database row yet must still accumulate XP."""

    @pytest.mark.asyncio
    async def test_marker_is_cleared_when_xp_is_written(self, cache):
        with patch("utils.database.get_user_data", AsyncMock(return_value=None)):
            assert await cache.get_user_data(USER_ID, GUILD_ID) is None

        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)

        data = await cache.get_user_data(USER_ID, GUILD_ID)
        assert data is not None, "the sentinel must not outlive the first XP write"
        assert "_exists" not in data
        assert data["xp"] == 20
        assert data["messages"] == 1

    @pytest.mark.asyncio
    async def test_message_xp_accumulates_for_a_brand_new_user(self, bot, mock_discord_message):
        """Regression: the running total used to reset to a single message's XP.

        Callers treat a cached ``_exists: False`` entry as "no data", so every
        message recomputed the total from zero until the 5-minute TTL expired -
        a new member kept only their most recent message's XP.
        """
        cache = LevelingCache(bot)
        service = LevelService(bot, cache=cache)

        gains: list[int] = []
        with (
            patch("utils.database.get_user_data", AsyncMock(return_value=None)),
            patch("utils.database.get_guild_settings", AsyncMock(return_value=None)),
        ):
            for _ in range(3):
                service._cooldowns.clear()  # simulate the 60s cooldown elapsing
                result = await service.award_message_xp(mock_discord_message)
                assert result is not None
                gains.append(result["xp_gained"])

        data = await cache.get_user_data(USER_ID, GUILD_ID)
        assert data is not None
        assert data["xp"] == sum(gains), "XP from earlier messages was lost"
        assert data["messages"] == 3

    @pytest.mark.asyncio
    async def test_existing_row_is_never_marked_as_missing(self, cache):
        existing = {"user_id": USER_ID, "guild_id": GUILD_ID, "xp": 500, "level": 2, "messages": 9}
        with patch("utils.database.get_user_data", AsyncMock(return_value=existing)):
            data = await cache.get_user_data(USER_ID, GUILD_ID)

        assert data == existing
        assert "_exists" not in data


class TestFlush:
    """Dirty entries are persisted in batches, then marked clean."""

    @pytest.mark.asyncio
    async def test_flush_persists_dirty_users_in_one_batch(self, cache, patched_db):
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)

        await cache.flush_all()

        patched_db.executemany.assert_awaited_once()
        sql, records = patched_db.executemany.await_args.args
        assert "INSERT INTO user_levels" in sql
        assert records[0][:6] == (USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)
        assert patched_db.rows[(GUILD_ID, USER_ID)]["xp"] == 20
        assert cache.get_metrics()["db_user_writes"] == 1

    @pytest.mark.asyncio
    async def test_clean_entries_are_not_written_again(self, cache, patched_db):
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)

        await cache.flush_all()
        await cache.flush_all()

        assert patched_db.executemany.await_count == 1, "a clean entry must not be re-flushed"

    @pytest.mark.asyncio
    async def test_second_flush_updates_the_existing_row(self, cache, patched_db):
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)
        await cache.flush_all()

        await cache.update_user_xp(USER_ID, GUILD_ID, 45, 0, 2, 1_060.0)
        await cache.flush_all()

        sql, _records = patched_db.executemany.await_args.args
        assert "UPDATE user_levels" in sql
        assert "AND updated_at = $8" in sql, "the write must be guarded by its token"
        assert patched_db.rows[(GUILD_ID, USER_ID)]["xp"] == 45

    @pytest.mark.asyncio
    async def test_failed_flush_keeps_entries_dirty_for_retry(self, cache, patched_db):
        await cache.update_user_xp(USER_ID, GUILD_ID, 20, 0, 1, 1_000.0)
        patched_db.raise_on_write = RuntimeError("database is down")

        await cache.flush_all()  # must not raise
        assert cache.get_metrics()["db_errors"] == 1

        patched_db.raise_on_write = None
        await cache.flush_all()

        assert patched_db.executemany.await_count == 2
        assert patched_db.rows[(GUILD_ID, USER_ID)]["xp"] == 20


class TestConcurrentWriters:
    """A flush must never revert a write made outside the bot."""

    @pytest.mark.asyncio
    async def test_external_change_wins_over_stale_cached_xp(self, cache, patched_db):
        """Regression: an admin action used to be overwritten by the flush.

        The dashboard writes `user_levels` directly. The cache held older values
        for up to 30s and then wrote them unconditionally, silently reverting the
        admin's change.
        """
        loaded = {"user_id": USER_ID, "guild_id": GUILD_ID, "xp": 100, "level": 0,
                  "messages": 5, "updated_at": 1_000}
        with patch("utils.database.get_user_data", AsyncMock(return_value=loaded)):
            await cache.get_user_data(USER_ID, GUILD_ID)

        # An admin sets the level through the dashboard while the member chats.
        patched_db.seed(GUILD_ID, USER_ID, updated_at=2_000, xp=5_675, level=10, messages=5)
        await cache.update_user_xp(USER_ID, GUILD_ID, 120, 0, 6, 1_060.0)

        with patch("utils.database.get_user_data", AsyncMock(return_value=dict(patched_db.rows[(GUILD_ID, USER_ID)]))):
            await cache.flush_all()

        row = patched_db.rows[(GUILD_ID, USER_ID)]
        assert row["xp"] == 5_675, "the admin's XP was overwritten"
        assert row["level"] == 10

        reloaded = await cache.get_user_data(USER_ID, GUILD_ID)
        assert reloaded["xp"] == 5_675

    @pytest.mark.asyncio
    async def test_our_write_lands_when_the_row_is_unchanged(self, cache, patched_db):
        loaded = {"user_id": USER_ID, "guild_id": GUILD_ID, "xp": 100, "level": 0,
                  "messages": 5, "updated_at": 1_000}
        patched_db.seed(GUILD_ID, USER_ID, updated_at=1_000, xp=100, level=0, messages=5)
        with patch("utils.database.get_user_data", AsyncMock(return_value=loaded)):
            await cache.get_user_data(USER_ID, GUILD_ID)

        await cache.update_user_xp(USER_ID, GUILD_ID, 120, 0, 6, 1_060.0)
        await cache.flush_all()

        row = patched_db.rows[(GUILD_ID, USER_ID)]
        assert row["xp"] == 120
        assert row["messages"] == 6

    @pytest.mark.asyncio
    async def test_deleted_row_is_not_resurrected(self, cache, patched_db):
        """A guild-wide reset deletes rows; the cache must not re-create them."""
        loaded = {"user_id": USER_ID, "guild_id": GUILD_ID, "xp": 100, "level": 0,
                  "messages": 5, "updated_at": 1_000}
        patched_db.seed(GUILD_ID, USER_ID, updated_at=1_000, xp=100, level=0, messages=5)
        with patch("utils.database.get_user_data", AsyncMock(return_value=loaded)):
            await cache.get_user_data(USER_ID, GUILD_ID)

        await cache.update_user_xp(USER_ID, GUILD_ID, 120, 0, 6, 1_060.0)
        del patched_db.rows[(GUILD_ID, USER_ID)]  # the reset happened

        await cache.flush_all()

        assert (GUILD_ID, USER_ID) not in patched_db.rows
        assert await cache.get_user_data(USER_ID, GUILD_ID) is None
