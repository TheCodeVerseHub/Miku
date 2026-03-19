"""
PostgreSQL Database Module for Miku Bot
Handles all database operations using asyncpg

Beginner notes:
- Required env var: `DATABASE_URL` (see `.env.example`).
- This file owns:
    - connection pool creation (`get_pool()`)
    - schema creation/migrations (`init_db()`)
    - all queries used by cogs (`get_user_data`, `update_user_xp`, ...)

Tables:
- `user_levels`: per-user XP/level/messages per guild
- `guild_settings`: per-guild configuration (level-up channel, cooldown, etc.)
- `role_rewards`: which role to award at which level

When adding a new feature that needs data:
1) Add columns/tables in `init_db()` (use IF NOT EXISTS / migrations)
2) Add a small helper function here (single responsibility)
3) Call that helper from your cog/service
"""

import asyncpg
import os
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('miku.database')

# Database connection pool
_pool: Optional[asyncpg.Pool] = None

# ============================================================================
# Connection Pool Management
# ============================================================================

async def get_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global _pool
    if _pool is None:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        # NOTE: `statement_cache_size=0` is intentional.
        # asyncpg caches prepared statements by default; after DDL (ALTER TABLE)
        # some servers can raise InvalidCachedStatementError. Disabling the cache
        # keeps behavior predictable for contributors.
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
            # Prevent InvalidCachedStatementError after DDL/migrations.
            statement_cache_size=0,
        )
        logger.info("Database connection pool created")
    return _pool

async def close_pool():
    """Close the database connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")

# ============================================================================
# Database Initialization
# ============================================================================

async def init_db() -> None:
    """Initialize database tables"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # User levels table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_levels (
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                xp BIGINT DEFAULT 0,
                level INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                last_message_time DOUBLE PRECISION DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        # Lightweight migrations for older schemas.
        # Hosted DBs might already contain tables created by a previous version.
        await conn.execute(
            "ALTER TABLE user_levels ADD COLUMN IF NOT EXISTS last_message_time DOUBLE PRECISION DEFAULT 0"
        )
        await conn.execute(
            "ALTER TABLE user_levels ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"
        )
        await conn.execute(
            "ALTER TABLE user_levels ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"
        )
        
        # Create index for leaderboard queries
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_levels_guild_xp 
            ON user_levels(guild_id, xp DESC)
        ''')
        
        # Guild settings table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id BIGINT PRIMARY KEY,
                levelup_channel_id BIGINT,
                xp_enabled BOOLEAN DEFAULT TRUE,
                min_xp INTEGER DEFAULT 15,
                max_xp INTEGER DEFAULT 25,
                cooldown_seconds INTEGER DEFAULT 60,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute(
            "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"
        )
        
        # Role rewards table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS role_rewards (
                guild_id BIGINT NOT NULL,
                level INTEGER NOT NULL,
                role_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (guild_id, level)
            )
        ''')
        
        # Create index for role rewards
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_role_rewards_guild 
            ON role_rewards(guild_id)
        ''')

        # DDL above can invalidate asyncpg's cached statement plans on this connection.
        # Refresh schema state before returning it to the pool.
        try:
            await conn.reload_schema_state()
        except Exception:
            # Not fatal; worst case asyncpg will raise and the caller can retry.
            logger.exception("Failed to reload schema state")
        
        logger.info("Database tables initialized")

# ============================================================================
# User Level Operations
# ============================================================================

async def get_user_data(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Get user's level data"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM user_levels WHERE user_id = $1 AND guild_id = $2',
            user_id, guild_id
        )
        return dict(row) if row else None

async def update_user_xp(
    user_id: int, 
    guild_id: int, 
    xp: int, 
    level: int, 
    messages: int, 
    last_message_time: float
) -> None:
    """Update or insert user XP data"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_levels 
                (user_id, guild_id, xp, level, messages, last_message_time, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                xp = EXCLUDED.xp,
                level = EXCLUDED.level,
                messages = EXCLUDED.messages,
                last_message_time = EXCLUDED.last_message_time,
                updated_at = NOW()
        ''', user_id, guild_id, xp, level, messages, last_message_time)

async def set_user_level(user_id: int, guild_id: int, level: int, xp: int) -> None:
    """Set user's level and XP (admin command)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_levels 
                (user_id, guild_id, xp, level, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                xp = EXCLUDED.xp,
                level = EXCLUDED.level,
                updated_at = NOW()
        ''', user_id, guild_id, xp, level)

async def get_user_rank(user_id: int, guild_id: int) -> Optional[int]:
    """Get user's rank in the guild (1-indexed)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT COUNT(*) + 1 as rank
            FROM user_levels
            WHERE guild_id = $1 AND xp > (
                SELECT COALESCE(xp, 0) FROM user_levels 
                WHERE user_id = $2 AND guild_id = $1
            )
        ''', guild_id, user_id)
        return row['rank'] if row else None

async def get_leaderboard(guild_id: int, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    """Get top users by XP in a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT user_id, xp, level, messages 
            FROM user_levels 
            WHERE guild_id = $1 
            ORDER BY xp DESC 
            LIMIT $2 OFFSET $3
        ''', guild_id, limit, offset)
        return [dict(row) for row in rows]

async def get_total_users(guild_id: int) -> int:
    """Get total number of users with XP in a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT COUNT(*) as count FROM user_levels WHERE guild_id = $1',
            guild_id
        )
        return row['count'] if row else 0

async def reset_user_data(user_id: int, guild_id: int) -> None:
    """Reset a user's level data"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            'DELETE FROM user_levels WHERE user_id = $1 AND guild_id = $2',
            user_id, guild_id
        )

async def reset_guild_data(guild_id: int) -> None:
    """Reset all level data for a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            'DELETE FROM user_levels WHERE guild_id = $1',
            guild_id
        )

# ============================================================================
# Guild Settings Operations
# ============================================================================

async def get_guild_settings(guild_id: int) -> Optional[Dict[str, Any]]:
    """Get guild settings"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM guild_settings WHERE guild_id = $1',
            guild_id
        )
        return dict(row) if row else None

async def set_levelup_channel(guild_id: int, channel_id: Optional[int]) -> None:
    """Set or remove the level-up announcement channel"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO guild_settings (guild_id, levelup_channel_id, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT(guild_id) DO UPDATE SET
                levelup_channel_id = EXCLUDED.levelup_channel_id,
                updated_at = NOW()
        ''', guild_id, channel_id)

async def toggle_xp_system(guild_id: int, enabled: bool) -> None:
    """Enable or disable XP system for a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO guild_settings (guild_id, xp_enabled, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT(guild_id) DO UPDATE SET
                xp_enabled = EXCLUDED.xp_enabled,
                updated_at = NOW()
        ''', guild_id, enabled)

# ============================================================================
# Role Rewards Operations
# ============================================================================

async def get_role_rewards(guild_id: int) -> List[Dict[str, Any]]:
    """Get all role rewards for a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT level, role_id FROM role_rewards WHERE guild_id = $1 ORDER BY level',
            guild_id
        )
        return [dict(row) for row in rows]

async def add_role_reward(guild_id: int, level: int, role_id: int) -> None:
    """Add or update a role reward for a level"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO role_rewards (guild_id, level, role_id)
            VALUES ($1, $2, $3)
            ON CONFLICT(guild_id, level) DO UPDATE SET
                role_id = EXCLUDED.role_id
        ''', guild_id, level, role_id)

async def remove_role_reward(guild_id: int, level: int):
    """Remove a role reward for a level"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            'DELETE FROM role_rewards WHERE guild_id = $1 AND level = $2',
            guild_id, level
        )
        return result != 'DELETE 0'

async def get_role_for_level(guild_id: int, level: int) -> Optional[int]:
    """Get role reward for a specific level"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT role_id FROM role_rewards WHERE guild_id = $1 AND level = $2',
            guild_id, level
        )
        return row['role_id'] if row else None

