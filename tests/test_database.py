"""
Tests for database operations (src/utils/database.py).

These are unit tests with mocked asyncpg pool. For integration tests
that require a real database, see tests/test_integration.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_pool():
    """Create a mock asyncpg pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    # Mock fetchrow
    conn.fetchrow = AsyncMock(return_value={"xp": 150, "level": 2, "messages": 5})
    # Mock fetch
    conn.fetch = AsyncMock(return_value=[
        {"user_id": 1, "xp": 500, "level": 5, "messages": 20},
        {"user_id": 2, "xp": 300, "level": 3, "messages": 15},
    ])
    # Mock execute
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    # Mock transaction
    conn.transaction = AsyncMock()
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock()

    pool.acquire = AsyncMock(return_value=conn)
    return pool


@pytest.mark.asyncio
async def test_get_user_data(mock_pool):
    """Test that get_user_data returns the correct dict."""
    with patch("src.utils.database._pool", mock_pool):
        from src.utils import database as db

        result = await db.get_user_data(123, 456)
        assert result is not None
        assert result["xp"] == 150
        assert result["level"] == 2


@pytest.mark.asyncio
async def test_get_user_rank(mock_pool):
    """Test that get_user_rank returns the rank."""
    with patch("src.utils.database._pool", mock_pool):
        from src.utils import database as db

        # Mock row with rank
        mock_pool.acquire.return_value.fetchrow = AsyncMock(
            return_value={"rank": 5}
        )
        rank = await db.get_user_rank(123, 456)
        assert rank == 5


@pytest.mark.asyncio
async def test_get_leaderboard(mock_pool):
    """Test leaderboard returns sorted list."""
    with patch("src.utils.database._pool", mock_pool):
        from src.utils import database as db

        rows = await db.get_leaderboard(456, limit=10, offset=0)
        assert len(rows) == 2
        assert rows[0]["xp"] == 500


@pytest.mark.asyncio
async def test_get_total_users(mock_pool):
    """Test total user count."""
    with patch("src.utils.database._pool", mock_pool):
        from src.utils import database as db

        mock_pool.acquire.return_value.fetchrow = AsyncMock(
            return_value={"count": 42}
        )
        count = await db.get_total_users(456)
        assert count == 42


@pytest.mark.asyncio
async def test_update_user_xp(mock_pool):
    """Test XP update calls the correct SQL."""
    with patch("src.utils.database._pool", mock_pool):
        from src.utils import database as db

        await db.update_user_xp(123, 456, 1000, 10, 50, 1234567890.0)

        # Verify the execute was called with the right parameters
        mock_pool.acquire.return_value.execute.assert_called_once()
        call_args = mock_pool.acquire.return_value.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO user_levels" in sql
        assert "ON CONFLICT" in sql


@pytest.mark.asyncio
async def test_get_guild_settings(mock_pool):
    """Test guild settings retrieval."""
    with patch("src.utils.database._pool", mock_pool):
        from src.utils import database as db

        mock_pool.acquire.return_value.fetchrow = AsyncMock(
            return_value={"guild_id": 456, "xp_enabled": True}
        )
        settings = await db.get_guild_settings(456)
        assert settings is not None
        assert settings["xp_enabled"] is True


@pytest.mark.asyncio
async def test_get_role_rewards(mock_pool):
    """Test role rewards retrieval."""
    with patch("src.utils.database._pool", mock_pool):
        from src.utils import database as db

        mock_pool.acquire.return_value.fetch = AsyncMock(
            return_value=[
                {"level": 5, "role_id": 111},
                {"level": 10, "role_id": 222},
            ]
        )
        rewards = await db.get_role_rewards(456)
        assert len(rewards) == 2
        assert rewards[0]["level"] == 5
