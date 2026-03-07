import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

# Create a connection pool
_pool = None

async def get_pool():
    """Get or create database connection pool"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool

async def close_pool():
    """Close the database connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

async def init_db():
    """Initialize the database with required tables"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_levels (
                user_id BIGINT,
                guild_id BIGINT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                last_message_time DOUBLE PRECISION DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id BIGINT PRIMARY KEY,
                levelup_channel_id BIGINT,
                updated_at DOUBLE PRECISION DEFAULT 0
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS role_rewards (
                guild_id BIGINT,
                level INTEGER,
                role_id BIGINT,
                PRIMARY KEY (guild_id, level)
            )
        ''')

async def get_user_data(user_id: int, guild_id: int):
    """Get user's level data"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM user_levels WHERE user_id = $1 AND guild_id = $2',
            user_id, guild_id
        )
        if row:
            return dict(row)
        return None

async def update_user_xp(user_id: int, guild_id: int, xp: int, level: int, messages: int, last_message_time: float):
    """Update or insert user XP data"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_levels (user_id, guild_id, xp, level, messages, last_message_time)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                xp = EXCLUDED.xp,
                level = EXCLUDED.level,
                messages = EXCLUDED.messages,
                last_message_time = EXCLUDED.last_message_time
        ''', user_id, guild_id, xp, level, messages, last_message_time)

async def get_leaderboard(guild_id: int, limit: int = 10):
    """Get top users by XP in a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            '''SELECT user_id, xp, level, messages 
               FROM user_levels 
               WHERE guild_id = $1 
               ORDER BY xp DESC 
               LIMIT $2''',
            guild_id, limit
        )
        return [dict(row) for row in rows]

async def get_user_rank(user_id: int, guild_id: int):
    """Get user's rank in the guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            '''SELECT COUNT(*) + 1 as rank
               FROM user_levels
               WHERE guild_id = $1 AND xp > (
                   SELECT xp FROM user_levels 
                   WHERE user_id = $2 AND guild_id = $1
               )''',
            guild_id, user_id
        )
        return row['rank'] if row else None

async def reset_user_data(user_id: int, guild_id: int):
    """Reset a user's level data"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            'DELETE FROM user_levels WHERE user_id = $1 AND guild_id = $2',
            user_id, guild_id
        )

async def reset_guild_data(guild_id: int):
    """Reset all level data for a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            'DELETE FROM user_levels WHERE guild_id = $1',
            guild_id
        )

# Guild Settings Functions
async def get_guild_settings(guild_id: int):
    """Get guild settings for leveling system"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM guild_settings WHERE guild_id = $1',
            guild_id
        )
        if row:
            return dict(row)
        return None

async def set_levelup_channel(guild_id: int, channel_id: int):
    """Set the level-up announcement channel"""
    import time
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO guild_settings (guild_id, levelup_channel_id, updated_at)
            VALUES ($1, $2, $3)
            ON CONFLICT(guild_id) DO UPDATE SET
                levelup_channel_id = EXCLUDED.levelup_channel_id,
                updated_at = EXCLUDED.updated_at
        ''', guild_id, channel_id, time.time())

async def get_role_rewards(guild_id: int):
    """Get all role rewards for a guild"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT level, role_id FROM role_rewards WHERE guild_id = $1 ORDER BY level',
            guild_id
        )
        return [dict(row) for row in rows]

async def add_role_reward(guild_id: int, level: int, role_id: int):
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
        await conn.execute(
            'DELETE FROM role_rewards WHERE guild_id = $1 AND level = $2',
            guild_id, level
        )

async def get_role_for_level(guild_id: int, level: int):
    """Get role reward for a specific level"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT role_id FROM role_rewards WHERE guild_id = $1 AND level = $2',
            guild_id, level
        )
        return row['role_id'] if row else None
