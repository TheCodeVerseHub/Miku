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
        async def _migrate_epoch_column_to_timestamp(table: str, column: str) -> None:
            """Convert legacy epoch columns (DOUBLE PRECISION) to TIMESTAMP.

            Older versions stored timestamps as epoch seconds (float). This migration
            makes the column consistent with the current schema (TIMESTAMP + NOW()).
            """

            row = await conn.fetchrow(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                  AND column_name = $2
                """,
                table,
                column,
            )

            if not row:
                return

            data_type = row["data_type"]

            # Expected types are timestamp without/with time zone. `NOW()` is
            # timestamptz but is implicitly castable to timestamp.
            if data_type in {"timestamp without time zone", "timestamp with time zone"}:
                return

            if data_type != "double precision":
                logger.warning(
                    "Unexpected type for %s.%s: %s (skipping migration)",
                    table,
                    column,
                    data_type,
                )
                return

            logger.info("Migrating %s.%s from DOUBLE PRECISION to TIMESTAMP", table, column)
            try:
                # Drop default first (often `0`) to avoid cast errors.
                await conn.execute(f'ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT')
            except Exception:
                # Default might not exist; continue.
                pass

            await conn.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMP USING to_timestamp({column})"
            )
            await conn.execute(f'ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT NOW()')

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

        # Migrate legacy epoch timestamp columns if present.
        await _migrate_epoch_column_to_timestamp("user_levels", "created_at")
        await _migrate_epoch_column_to_timestamp("user_levels", "updated_at")
        
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
        await conn.execute(
            "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS xp_enabled BOOLEAN DEFAULT TRUE"
        )
        await conn.execute(
            "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS min_xp INTEGER DEFAULT 15"
        )
        await conn.execute(
            "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS max_xp INTEGER DEFAULT 25"
        )
        await conn.execute(
            "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS cooldown_seconds INTEGER DEFAULT 60"
        )

        await _migrate_epoch_column_to_timestamp("guild_settings", "created_at")
        await _migrate_epoch_column_to_timestamp("guild_settings", "updated_at")
        
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

        # ── XP settings (separate from general guild_settings) ──────────
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS xp_settings (
                guild_id BIGINT PRIMARY KEY,
                formula_name VARCHAR(64) DEFAULT 'quadratic',
                min_xp INTEGER DEFAULT 15,
                max_xp INTEGER DEFAULT 25,
                cooldown_seconds INTEGER DEFAULT 60,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute(
            "ALTER TABLE xp_settings ADD COLUMN IF NOT EXISTS formula_name VARCHAR(64) DEFAULT 'quadratic'"
        )

        # Migrate existing values from guild_settings → xp_settings
        await conn.execute('''
            INSERT INTO xp_settings (guild_id, min_xp, max_xp, cooldown_seconds)
                SELECT guild_id, min_xp, max_xp, cooldown_seconds
                FROM guild_settings
                WHERE guild_id NOT IN (SELECT guild_id FROM xp_settings)
            ON CONFLICT (guild_id) DO NOTHING
        ''')

        # ── XP multipliers ──────────────────────────────────────────────
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS xp_multipliers (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                target_type VARCHAR(32) NOT NULL,
                target_id BIGINT NOT NULL,
                multiplier NUMERIC(5,2) NOT NULL DEFAULT 1.00,
                label VARCHAR(128),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(guild_id, target_type, target_id)
            )
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_xp_multipliers_guild
            ON xp_multipliers(guild_id)
        ''')

        # ── XP restrictions ─────────────────────────────────────────────
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS xp_restrictions (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                restriction_type VARCHAR(32) NOT NULL,
                target_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_xp_restrictions_guild
            ON xp_restrictions(guild_id)
        ''')

        # ── XP log (time-series) ────────────────────────────────────────
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS xp_log (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                source VARCHAR(32) NOT NULL,
                reason VARCHAR(512),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_xp_log_guild
            ON xp_log(guild_id, created_at DESC)
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_xp_log_user
            ON xp_log(guild_id, user_id, created_at DESC)
        ''')

        # ── Audit log ───────────────────────────────────────────────────
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                admin_id BIGINT NOT NULL,
                action VARCHAR(64) NOT NULL,
                details JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_audit_log_guild
            ON audit_log(guild_id, created_at DESC)
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
# Departed User Cleanup
# ============================================================================

async def clean_departed_users(guild_id: int, active_user_ids: set) -> Dict[str, int]:
    """Remove leveling data for users who are no longer guild members.

    Compares stored user IDs against the provided set of active member IDs,
    then deletes all leveling-related rows for departed members atomically.

    Returns:
        dict with keys: total_checked, total_removed, total_remaining
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                'SELECT user_id FROM user_levels WHERE guild_id = $1',
                guild_id,
            )
            db_user_ids = {row["user_id"] for row in rows}

            total_checked = len(db_user_ids)
            departed_ids = list(db_user_ids - active_user_ids)

            if not departed_ids:
                return {
                    "total_checked": total_checked,
                    "total_removed": 0,
                    "total_remaining": total_checked,
                }

            for table in ("user_levels", "xp_log", "audit_log"):
                await conn.execute(
                    f"DELETE FROM {table} WHERE guild_id = $1 AND user_id = ANY($2::bigint[])",
                    guild_id,
                    departed_ids,
                )

            return {
                "total_checked": total_checked,
                "total_removed": len(departed_ids),
                "total_remaining": total_checked - len(departed_ids),
            }


async def delete_user_leveling_data(user_id: int, guild_id: int) -> None:
    """Delete all leveling-related data for a single user in a guild.

    Used by the automatic ``on_member_remove`` listener so departed users
    disappear from leaderboard / dashboard immediately.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for table in ("user_levels", "xp_log", "audit_log"):
                await conn.execute(
                    f"DELETE FROM {table} WHERE user_id = $1 AND guild_id = $2",
                    user_id,
                    guild_id,
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

# ============================================================================
# XP Settings Operations
# ============================================================================

async def get_xp_settings(guild_id: int) -> Optional[Dict[str, Any]]:
    """Get XP-specific settings for a guild."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM xp_settings WHERE guild_id = $1',
            guild_id
        )
        return dict(row) if row else None

async def upsert_xp_settings(guild_id: int, **kwargs) -> None:
    """Insert or update XP settings.

    Accepted kwargs: formula_name, min_xp, max_xp, cooldown_seconds.
    """
    cols = []
    vals = []
    idx = 1
    for key in ("formula_name", "min_xp", "max_xp", "cooldown_seconds"):
        if key in kwargs:
            cols.append(f"{key} = ${idx}")
            vals.append(kwargs[key])
            idx += 1
    if not cols:
        return
    set_clause = ", ".join(cols)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f'''
            INSERT INTO xp_settings (guild_id, updated_at)
            VALUES ($1, NOW())
            ON CONFLICT (guild_id) DO UPDATE SET
                {set_clause},
                updated_at = NOW()
        ''', guild_id, *vals)

# ============================================================================
# XP Multiplier Operations
# ============================================================================

async def get_xp_multipliers(guild_id: int) -> List[Dict[str, Any]]:
    """Get all XP multipliers for a guild."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT id, target_type, target_id, multiplier, label '
            'FROM xp_multipliers WHERE guild_id = $1 ORDER BY id',
            guild_id
        )
        return [dict(r) for r in rows]

async def add_xp_multiplier(
    guild_id: int,
    target_type: str,
    target_id: int,
    multiplier: float,
    label: Optional[str] = None,
) -> None:
    """Add or update an XP multiplier."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO xp_multipliers (guild_id, target_type, target_id, multiplier, label)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, target_type, target_id) DO UPDATE SET
                multiplier = EXCLUDED.multiplier,
                label = EXCLUDED.label
        ''', guild_id, target_type, target_id, multiplier, label)

async def remove_xp_multiplier(guild_id: int, multiplier_id: int) -> bool:
    """Remove an XP multiplier by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            'DELETE FROM xp_multipliers WHERE guild_id = $1 AND id = $2',
            guild_id, multiplier_id
        )
        return result != 'DELETE 0'

# ============================================================================
# XP Restriction Operations
# ============================================================================

async def get_xp_restrictions(guild_id: int) -> List[Dict[str, Any]]:
    """Get all XP restrictions for a guild."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT id, restriction_type, target_id '
            'FROM xp_restrictions WHERE guild_id = $1 ORDER BY id',
            guild_id
        )
        return [dict(r) for r in rows]

async def add_xp_restriction(guild_id: int, restriction_type: str, target_id: int) -> None:
    """Add an XP restriction."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO xp_restrictions (guild_id, restriction_type, target_id)
            VALUES ($1, $2, $3)
        ''', guild_id, restriction_type, target_id)

async def remove_xp_restriction(guild_id: int, restriction_id: int) -> bool:
    """Remove an XP restriction by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            'DELETE FROM xp_restrictions WHERE guild_id = $1 AND id = $2',
            guild_id, restriction_id
        )
        return result != 'DELETE 0'

# ============================================================================
# XP Log Operations
# ============================================================================

async def insert_xp_log(guild_id: int, user_id: int, amount: int, source: str, reason: str = "") -> None:
    """Record an XP change in the log."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO xp_log (guild_id, user_id, amount, source, reason)
            VALUES ($1, $2, $3, $4, NULLIF($5, ''))
        ''', guild_id, user_id, amount, source, reason)

async def get_xp_log(
    guild_id: int,
    limit: int = 100,
    offset: int = 0,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get recent XP log entries for a guild."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if source:
            rows = await conn.fetch(
                'SELECT id, user_id, amount, source, reason, created_at '
                'FROM xp_log WHERE guild_id = $1 AND source = $2 '
                'ORDER BY created_at DESC LIMIT $3 OFFSET $4',
                guild_id, source, limit, offset
            )
        else:
            rows = await conn.fetch(
                'SELECT id, user_id, amount, source, reason, created_at '
                'FROM xp_log WHERE guild_id = $1 '
                'ORDER BY created_at DESC LIMIT $2 OFFSET $3',
                guild_id, limit, offset
            )
        return [dict(r) for r in rows]

# ============================================================================
# Audit Log Operations
# ============================================================================

async def insert_audit_log(
    guild_id: int,
    user_id: int,
    admin_id: int,
    action: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an admin action in the audit log."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO audit_log (guild_id, user_id, admin_id, action, details)
            VALUES ($1, $2, $3, $4, $5::jsonb)
        ''', guild_id, user_id, admin_id, action, details or {})

async def get_audit_log(
    guild_id: int,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get recent audit log entries for a guild."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT id, user_id, admin_id, action, details, created_at '
            'FROM audit_log WHERE guild_id = $1 '
            'ORDER BY created_at DESC LIMIT $2 OFFSET $3',
            guild_id, limit, offset
        )
        return [dict(r) for r in rows]

