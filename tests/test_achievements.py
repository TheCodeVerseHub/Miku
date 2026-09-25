"""Tests for the achievement system (`cogs/achievements.py`).

The behaviour that matters, and that the previous implementation got wrong:

- Achievements were checked by nothing at all: `check_achievements` had no
  caller and the cog had no `on_message` listener, so the whole subsystem was
  dead. There is now a throttled listener.
- The XP reward was only written to `xp_log`. The member's `user_levels` row was
  never touched, so the bot announced "+100 XP" and the total stayed the same.
  Rewards now go through `LevelService.add_xp`.

Several tests here use a fake `LevelingCache` so a reward has a real destination
to land in - that is what makes "the XP actually reached the member" assertable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cogs.achievements import ACHIEVEMENTS, Achievements
from services.level_service import LevelService


class _AsyncCM:
    """Minimal async context manager, standing in for `pool.acquire()`."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _AsyncCM(self._conn)


class _FakeLevelingCache:
    """Stand-in for `LevelingCache` that keeps the member row in memory."""

    def __init__(self, row=None):
        self.row = dict(row) if row else None
        self.writes: list[tuple] = []
        self.xp_logs: list[tuple] = []

    async def get_user_data(self, user_id: int, guild_id: int):
        return self.row

    async def update_user_xp(
        self, user_id, guild_id, xp, level, messages, last_message_time
    ) -> None:
        self.row = {
            "user_id": user_id,
            "guild_id": guild_id,
            "xp": xp,
            "level": level,
            "messages": messages,
            "last_message_time": last_message_time,
        }
        self.writes.append((xp, level, messages))

    async def insert_xp_log(self, guild_id, user_id, amount, source, reason="") -> None:
        self.xp_logs.append((guild_id, user_id, amount, source, reason))


def _build(mock_bot, row=None, unlocked_rows=()):
    """Wire a cog onto a fake cache + fake pool and return the interesting bits."""
    cache = _FakeLevelingCache(row)
    cog = Achievements(mock_bot)
    cog._service = LevelService(mock_bot, cache=cache)

    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=list(unlocked_rows))
    conn.executemany = AsyncMock()

    return cog, cache, conn, patch("utils.database.get_pool", AsyncMock(return_value=_FakePool(conn)))


# ──────────────────────────────────────────────────────────────────────
# Threshold evaluation
# ──────────────────────────────────────────────────────────────────────


def test_pending_only_returns_achievements_whose_threshold_is_met(mock_bot):
    cog = Achievements(mock_bot)

    pending = cog._pending(set(), {"level": 5, "messages": 99, "total_xp": 0, "voice_hours": 0})
    assert [a.id for a in pending] == ["level_5"]


def test_pending_skips_already_unlocked(mock_bot):
    cog = Achievements(mock_bot)

    pending = cog._pending({"level_5"}, {"level": 10, "messages": 0, "total_xp": 0})
    assert [a.id for a in pending] == ["level_10"]


def test_every_achievement_check_reads_a_stat_that_exists(mock_bot):
    """Guard against a typo'd `check` silently disabling an achievement."""
    cog = Achievements(mock_bot)
    stats = {"level": 1, "messages": 1, "total_xp": 1, "voice_hours": 1}

    missing = {a.check for a in ACHIEVEMENTS} - set(stats)
    assert not missing, f"achievements reference unknown stats: {sorted(missing)}"
    assert cog._pending(set(), stats)  # sanity: at least one matches a 1/1/1/1 member


@pytest.mark.asyncio
async def test_member_below_every_threshold_writes_nothing(mock_bot):
    cog, cache, conn, pool_patch = _build(mock_bot, row={"xp": 5, "level": 0, "messages": 3})

    with pool_patch:
        stats = await cog._collect_stats(1, 2)
        unlocked = await cog.check_achievements(1, 2, stats)

    assert unlocked == []
    assert cache.writes == []
    conn.executemany.assert_not_awaited()
    # Only the unlocked-id lookup ran; the "locked" set is cached from then on.
    assert conn.fetch.await_count == 1


# ──────────────────────────────────────────────────────────────────────
# Rewards
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unlock_inserts_ids_and_credits_the_reward_to_the_member(mock_bot):
    cog, cache, conn, pool_patch = _build(mock_bot, row={"xp": 0, "level": 0, "messages": 100})

    with pool_patch:
        unlocked = await cog.check_achievements(1, 2, await cog._collect_stats(1, 2))

    assert [a.id for a in unlocked] == ["msg_100"]

    sql, rows = conn.executemany.await_args.args
    assert "ON CONFLICT DO NOTHING" in sql
    assert [row[2] for row in rows] == ["msg_100"]

    # The reward reached the member's row (this is what the old code failed to do).
    assert cache.row["xp"] == 10
    assert cache.xp_logs[-1][3] == "EVENT"


@pytest.mark.asyncio
async def test_unlocked_achievement_is_not_rewarded_twice(mock_bot):
    cog, cache, conn, pool_patch = _build(
        mock_bot,
        row={"xp": 10, "level": 0, "messages": 100},
        unlocked_rows=[{"achievement_id": "msg_100"}],
    )

    with pool_patch:
        unlocked = await cog.check_achievements(1, 2, await cog._collect_stats(1, 2))

    assert unlocked == []
    assert cache.writes == []
    conn.executemany.assert_not_awaited()


@pytest.mark.asyncio
async def test_message_listener_announces_the_unlock(mock_bot, mock_discord_message):
    cog, cache, _conn, pool_patch = _build(mock_bot, row={"xp": 0, "level": 0, "messages": 100})

    with pool_patch:
        await cog.on_message(mock_discord_message)

    mock_discord_message.channel.send.assert_awaited_once()
    embed = mock_discord_message.channel.send.await_args.kwargs["embed"]
    assert "Chatter" in embed.description
    assert cache.row["xp"] == 10


@pytest.mark.asyncio
async def test_bot_messages_are_ignored(mock_bot, mock_discord_message):
    cog, cache, _conn, pool_patch = _build(mock_bot, row={"xp": 0, "level": 0, "messages": 100})
    mock_discord_message.author.bot = True

    with pool_patch:
        await cog.on_message(mock_discord_message)

    mock_discord_message.channel.send.assert_not_awaited()
    assert cache.writes == []


@pytest.mark.asyncio
async def test_throttle_collapses_a_burst_of_messages(mock_bot, mock_discord_message):
    """A hundred messages in a row must not become a hundred evaluations."""
    cog, cache, conn, pool_patch = _build(mock_bot, row={"xp": 0, "level": 0, "messages": 100})

    with pool_patch:
        await cog.on_message(mock_discord_message)

        # A second, immediately-following message is throttled away.
        mock_discord_message.channel.send.reset_mock()
        cache.row["messages"] = 500
        await cog.on_message(mock_discord_message)
        assert conn.executemany.await_count == 1
        assert cache.row["xp"] == 10  # msg_500 was not evaluated yet
        mock_discord_message.channel.send.assert_not_awaited()

        # Once the window passes the milestone is picked up.
        cog._last_checked.clear()
        await cog.on_message(mock_discord_message)

    assert conn.executemany.await_count == 2
    assert [row[2] for row in conn.executemany.await_args.args[1]] == ["msg_500"]
    assert cache.row["xp"] == 10 + 50


@pytest.mark.asyncio
async def test_listener_failure_never_breaks_the_message_flow(mock_bot, mock_discord_message):
    cog, _cache, _conn, pool_patch = _build(mock_bot, row={"xp": 0, "level": 0, "messages": 100})

    with pool_patch, patch.object(cog, "_collect_stats", AsyncMock(side_effect=RuntimeError("boom"))):
        await cog.on_message(mock_discord_message)  # must not raise

    mock_discord_message.channel.send.assert_not_awaited()
