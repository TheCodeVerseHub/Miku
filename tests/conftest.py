"""
Shared test fixtures and configuration for Miku tests.

Provides:
- Database fixtures (asyncpg test pool)
- Mock Discord bot fixtures
- Mock HTTP clients for GitHub/Discord API
- Sample data factories
"""

import asyncio
import os
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (skip with -m 'not slow')")
    config.addinivalue_line("markers", "integration: marks tests that need a database")
    config.addinivalue_line("markers", "security: marks security-related tests")


# ──────────────────────────────────────────────────────────────────────
# Database fixtures (require a running PostgreSQL instance)
# ──────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_pool():
    """Create a database connection pool for testing.

    Requires DATABASE_URL environment variable to be set.
    Skips the test if not available.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    import asyncpg

    pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=2,
        statement_cache_size=0,
        command_timeout=10,
    )
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def clean_db(db_pool):
    """Ensure database tables exist and are clean before each test."""
    async with db_pool.acquire() as conn:
        # Create tables if they don't exist
        from src.utils import database as db

        # Monkey-patch the pool
        original = db._pool
        db._pool = db_pool

        await db.init_db()

        # Clean all tables
        for table in ("user_levels", "guild_settings", "role_rewards", "xp_log", "audit_log", "xp_settings", "xp_multipliers", "xp_restrictions"):
            await conn.execute(f"DELETE FROM {table}")

        yield

        # Restore original pool
        db._pool = original


# ──────────────────────────────────────────────────────────────────────
# Mock Discord fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_discord_user():
    """Create a mock Discord user."""
    user = MagicMock()
    user.id = 123456789012345678
    user.name = "TestUser"
    user.display_name = "TestUser"
    user.bot = False
    user.avatar = MagicMock()
    user.avatar.url = "https://cdn.discordapp.com/avatars/123456789012345678/abc.png"
    user.default_avatar = MagicMock()
    user.default_avatar.url = "https://cdn.discordapp.com/embed/avatars/0.png"
    user.display_avatar = MagicMock()
    user.display_avatar.url = "https://cdn.discordapp.com/avatars/123456789012345678/abc.png"
    user.mention = "<@123456789012345678>"
    return user


@pytest.fixture
def mock_discord_member(mock_discord_user):
    """Create a mock Discord guild member."""
    member = MagicMock()
    member.id = mock_discord_user.id
    member.name = mock_discord_user.name
    member.display_name = mock_discord_user.display_name
    member.bot = False
    member.avatar = mock_discord_user.avatar
    member.display_avatar = mock_discord_user.display_avatar
    member.mention = mock_discord_user.mention

    member.guild = MagicMock()
    member.guild.id = 987654321098765432
    member.guild.name = "Test Guild"
    member.guild.get_member = MagicMock(return_value=member)

    member.roles = []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()

    return member


@pytest.fixture
def mock_discord_message(mock_discord_member):
    """Create a mock Discord message."""
    message = MagicMock()
    message.id = 111111111111111111
    message.author = mock_discord_member
    message.guild = mock_discord_member.guild
    message.channel = MagicMock()
    message.channel.id = 222222222222222222
    message.channel.name = "general"
    message.channel.send = AsyncMock()
    message.content = "Hello, world!"
    message.created_at = MagicMock()
    message.created_at.timestamp = MagicMock(return_value=1000000.0)
    return message


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789012345678
    bot.user.name = "Miku Test"
    bot.guilds = []
    return bot


# ──────────────────────────────────────────────────────────────────────
# Formula test data
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_formula_data() -> Dict[str, Any]:
    """Sample XP/level data for formula tests."""
    return {
        "quadratic": {
            "level_1_xp": 0,
            "level_5_xp": 155 * 5,  # Total for levels 1-5
            "level_10_xp": 3850,
            "level_50_xp": 89250,
        }
    }


# ──────────────────────────────────────────────────────────────────────
# HTTP mock fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_http_session():
    """Create a mock aiohttp ClientSession."""
    import aiohttp

    session = MagicMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.close = AsyncMock()
    return session
