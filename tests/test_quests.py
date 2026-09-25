"""Tests for the quest system (`cogs/quests.py`).

The important regression here is replay: `/claim` must award a quest's XP at
most once, no matter how many times it is invoked. Before the fix the claim ran
an unconditional `UPDATE ... SET claimed = TRUE`, the in-memory quest was never
marked as claimed, and every `/claim all` handed out the reward again.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cogs.quests import QUEST_TEMPLATES, Quest, Quests


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


@pytest.fixture
def cog(mock_bot) -> Quests:
    return Quests(mock_bot)


@pytest.fixture
def completed_quest() -> Quest:
    template = next(t for t in QUEST_TEMPLATES if t["type"] == "send_messages")
    quest = Quest(template, "daily")
    quest.progress = quest.target_amount  # completed
    return quest


def _patch_db(fetchrow_result):
    """Patch the quest cog's database calls and return the mocks."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)

    return conn, (
        patch("utils.database.get_pool", AsyncMock(return_value=_FakePool(conn))),
        patch("utils.database.get_user_data", AsyncMock(return_value=None)),
        patch("utils.database.update_user_xp", AsyncMock()),
        patch("utils.database.insert_xp_log", AsyncMock()),
    )


@pytest.mark.asyncio
async def test_incomplete_quest_never_touches_the_database(cog, completed_quest):
    completed_quest.progress = 0

    with patch("utils.database.get_pool", AsyncMock()) as get_pool:
        assert await cog._claim_quest(1, 2, completed_quest) is False
        get_pool.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_awards_when_the_row_transitions_to_claimed(cog, completed_quest):
    _conn, patches = _patch_db({"progress": completed_quest.target_amount})
    with patches[0], patches[1], patches[2] as update_xp, patches[3] as log_xp:
        assert await cog._claim_quest(1, 2, completed_quest) is True

    update_xp.assert_awaited_once()
    log_xp.assert_awaited_once()
    # XP is applied on top of the stored value.
    _user_id, _guild_id, new_xp = update_xp.await_args.args[:3]
    assert new_xp == completed_quest.xp_reward


@pytest.mark.asyncio
async def test_replayed_claim_does_not_award_xp_again(cog, completed_quest):
    """A second `/claim` for the same quest must be a no-op."""
    # The guarded UPDATE affects no rows the second time round.
    _conn, patches = _patch_db(None)
    with patches[0], patches[1], patches[2] as update_xp, patches[3] as log_xp:
        assert await cog._claim_quest(1, 2, completed_quest) is False

    update_xp.assert_not_awaited()
    log_xp.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_sql_guards_on_unclaimed_rows(cog, completed_quest):
    """Lock in the guard: the UPDATE must be conditional and report affected rows."""
    conn, patches = _patch_db({"progress": 1})
    with patches[0], patches[1], patches[2], patches[3]:
        await cog._claim_quest(1, 2, completed_quest)

    sql = conn.fetchrow.await_args.args[0]
    assert "claimed = FALSE" in sql, "the UPDATE must only match unclaimed rows"
    assert "RETURNING" in sql, "the caller must be able to detect a no-op claim"


@pytest.mark.asyncio
async def test_claim_preserves_last_message_time(cog, completed_quest):
    """Claiming must not clobber the stored cooldown timestamp with 0."""
    _conn, patches = _patch_db({"progress": 1})
    existing = {"xp": 100, "level": 0, "messages": 3, "last_message_time": 12345.0}
    with (
        patches[0],
        patch("utils.database.get_user_data", AsyncMock(return_value=existing)),
        patches[2] as update_xp,
        patches[3],
    ):
        await cog._claim_quest(1, 2, completed_quest)

    _user_id, _guild_id, _xp, _level, _messages, last_message_time = update_xp.await_args.args
    assert last_message_time == 12345.0
