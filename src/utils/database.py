import aiosqlite
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "leveling.db"

async def init_db():
    """Initialize the database with required tables"""
    # Create data directory if it doesn't exist
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_levels (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                last_message_time REAL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        await db.commit()

async def get_user_data(user_id: int, guild_id: int):
    """Get user's level data"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM user_levels WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def update_user_xp(user_id: int, guild_id: int, xp: int, level: int, messages: int, last_message_time: float):
    """Update or insert user XP data"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO user_levels (user_id, guild_id, xp, level, messages, last_message_time)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                xp = excluded.xp,
                level = excluded.level,
                messages = excluded.messages,
                last_message_time = excluded.last_message_time
        ''', (user_id, guild_id, xp, level, messages, last_message_time))
        await db.commit()

async def get_leaderboard(guild_id: int, limit: int = 10):
    """Get top users by XP in a guild"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT user_id, xp, level, messages 
               FROM user_levels 
               WHERE guild_id = ? 
               ORDER BY xp DESC 
               LIMIT ?''',
            (guild_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_user_rank(user_id: int, guild_id: int):
    """Get user's rank in the guild"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            '''SELECT COUNT(*) + 1 as rank
               FROM user_levels
               WHERE guild_id = ? AND xp > (
                   SELECT xp FROM user_levels 
                   WHERE user_id = ? AND guild_id = ?
               )''',
            (guild_id, user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def reset_user_data(user_id: int, guild_id: int):
    """Reset a user's level data"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'DELETE FROM user_levels WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        )
        await db.commit()

async def reset_guild_data(guild_id: int):
    """Reset all level data for a guild"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'DELETE FROM user_levels WHERE guild_id = ?',
            (guild_id,)
        )
        await db.commit()
