"""In-memory cache for the leveling system with periodic PostgreSQL persistence.

Goal: eliminate per-message DB queries. XP changes accumulate in memory and are
flushed to PostgreSQL in batches on a configurable interval (default 30 s).

Design:
- User data cached with 5-minute TTL; dirty entries flushed periodically.
- Guild settings cached with 2-minute TTL (read-heavy, rarely written).
- XP log entries buffered and flushed in batches.
- Per-user asyncio.Lock prevents concurrent mutations on the same user.
- Exponential backoff on repeated DB failures with rate-limited logging.
- All observability counters are periodic, not per-message.

Usage (in LevelService.__init__ or cog_load):
    self.cache = LevelingCache(bot, flush_interval=30)
    await self.cache.start()
    # …
    await self.cache.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from utils import database as db

logger = logging.getLogger("miku.db_cache")

# ── Metrics (counters, rate-limited log) ─────────────────────────────

_METRICS_LOG_INTERVAL = 120  # seconds between metrics log lines


class _Metrics:
    """Lightweight counters flushed periodically to the log."""

    __slots__ = (
        "user_cache_hits",
        "user_cache_misses",
        "guild_cache_hits",
        "guild_cache_misses",
        "db_user_writes",
        "db_guild_writes",
        "db_xp_logs_flushed",
        "db_errors",
        "retry_attempts",
        "pending_updates",
        "_last_log",
    )

    def __init__(self) -> None:
        self.user_cache_hits = 0
        self.user_cache_misses = 0
        self.guild_cache_hits = 0
        self.guild_cache_misses = 0
        self.db_user_writes = 0
        self.db_guild_writes = 0
        self.db_xp_logs_flushed = 0
        self.db_errors = 0
        self.retry_attempts = 0
        self.pending_updates = 0
        self._last_log = 0.0

    def log_if_due(self, cache_size: int) -> None:
        now = time.time()
        if now - self._last_log < _METRICS_LOG_INTERVAL:
            return
        self._last_log = now
        pending = (
            self.db_user_writes
            + self.db_guild_writes
            + self.db_xp_logs_flushed
        )
        logger.info(
            "cache_metrics: size=%d user_hits=%d misses=%d "
            "guild_hits=%d misses=%d db_writes=%d xp_logs=%d "
            "db_errors=%d retries=%d",
            cache_size,
            self.user_cache_hits,
            self.user_cache_misses,
            self.guild_cache_hits,
            self.guild_cache_misses,
            pending,
            self.db_xp_logs_flushed,
            self.db_errors,
            self.retry_attempts,
        )
        # Reset interval-based counters
        self.user_cache_hits = 0
        self.user_cache_misses = 0
        self.guild_cache_hits = 0
        self.guild_cache_misses = 0
        self.db_user_writes = 0
        self.db_guild_writes = 0
        self.db_xp_logs_flushed = 0

    def snapshot(self, cache_size: int) -> Dict[str, Any]:
        """Return a copy of counters without resetting them."""
        return {
            "cache_size": cache_size,
            "user_cache_hits": self.user_cache_hits,
            "user_cache_misses": self.user_cache_misses,
            "guild_cache_hits": self.guild_cache_hits,
            "guild_cache_misses": self.guild_cache_misses,
            "db_user_writes": self.db_user_writes,
            "db_guild_writes": self.db_guild_writes,
            "db_xp_logs_flushed": self.db_xp_logs_flushed,
            "db_errors": self.db_errors,
            "retry_attempts": self.retry_attempts,
            "pending_updates": self.pending_updates,
        }


# ── Cache entry ──────────────────────────────────────────────────────


class _UserCacheEntry:
    """Cached user leveling data with dirty-tracking."""

    __slots__ = ("data", "loaded_at", "dirty", "new_user")

    def __init__(
        self,
        data: Dict[str, Any],
        *,
        new_user: bool = False,
    ) -> None:
        self.data = data
        self.loaded_at = time.time()
        self.dirty = False
        self.new_user = new_user


class _GuildConfigEntry:
    """Cached guild XP settings."""

    __slots__ = ("data", "loaded_at")

    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data
        self.loaded_at = time.time()


# ── Main cache class ─────────────────────────────────────────────────


class LevelingCache:
    """In-memory cache that sits between LevelService and PostgreSQL.

    Responsibilities:
    - Cache user leveling data (5-minute TTL, max 5 000 entries).
    - Cache guild XP settings (2-minute TTL, max 500 entries).
    - Accumulate XP changes in memory (dirty-write tracking).
    - Periodically flush dirty entries to PostgreSQL in batched queries.
    - Buffer XP log entries and flush them in batches.
    - Handle DB failures gracefully with exponential backoff.
    - Expose observability counters for debugging.
    """

    # Configuration defaults
    USER_CACHE_TTL = 300  # 5 minutes
    GUILD_CONFIG_TTL = 120  # 2 minutes
    MAX_USER_CACHE = 5000
    MAX_GUILD_CACHE = 500
    DEFAULT_FLUSH_INTERVAL = 30  # seconds

    def __init__(self, bot, flush_interval: int = DEFAULT_FLUSH_INTERVAL):
        self.bot = bot
        self._flush_interval = flush_interval

        # ── User data cache: (guild_id, user_id) -> _UserCacheEntry ──
        self._user_cache: Dict[Tuple[int, int], _UserCacheEntry] = {}
        self._user_locks: Dict[Tuple[int, int], asyncio.Lock] = {}
        self._user_locks_lock = asyncio.Lock()  # protects the locks dict

        # ── Guild config cache: guild_id -> _GuildConfigEntry ────────
        self._guild_cache: Dict[int, _GuildConfigEntry] = {}

        # ── XP log buffer ────────────────────────────────────────────
        self._pending_xp_logs: List[Tuple[int, int, int, str, str]] = []

        # ── Background task ──────────────────────────────────────────
        self._flush_task: Optional[asyncio.Task] = None

        # ── Error handling ───────────────────────────────────────────
        self._backoff_until = 0.0  # timestamp: skip flush if currently in backoff
        self._consecutive_errors = 0

        # ── Metrics ──────────────────────────────────────────────────
        self.metrics = _Metrics()

    # ── Lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background flush task."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info(
                "LevelingCache started (flush_interval=%ds, user_ttl=%ds, guild_ttl=%ds)",
                self._flush_interval,
                self.USER_CACHE_TTL,
                self.GUILD_CONFIG_TTL,
            )

    async def shutdown(self) -> None:
        """Cancel background task and flush all pending data."""
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush_all()
        logger.info("LevelingCache shut down")

    async def _get_user_lock(self, guild_id: int, user_id: int) -> asyncio.Lock:
        """Get or create a per-user asyncio.Lock.

        Uses ``_user_locks_lock`` to prevent two concurrent coroutines from
        creating separate Lock instances for the same user.
        """
        key = (guild_id, user_id)
        async with self._user_locks_lock:
            lock = self._user_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._user_locks[key] = lock
            return lock

    # ── User data cache ─────────────────────────────────────────────

    async def get_user_data(
        self, user_id: int, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get user leveling data, using cache when available."""
        key = (guild_id, user_id)
        entry = self._user_cache.get(key)

        if entry is not None:
            age = time.time() - entry.loaded_at
            if age < self.USER_CACHE_TTL:
                self.metrics.user_cache_hits += 1
                return entry.data
            # TTL expired — treat as miss
            self.metrics.user_cache_misses += 1
        else:
            self.metrics.user_cache_misses += 1

        # Fetch from database
        try:
            data = await db.get_user_data(user_id, guild_id)
        except Exception:
            logger.exception("Failed to fetch user data from DB (user=%s guild=%s)", user_id, guild_id)
            self.metrics.db_errors += 1
            # If cache exists but expired, return stale data rather than None
            if entry is not None:
                logger.debug("Returning stale cached data for user=%s guild=%s", user_id, guild_id)
                return entry.data
            return None

        if data is not None:
            self._user_cache[key] = _UserCacheEntry(data)
            # Evict oldest if over max
            if len(self._user_cache) > self.MAX_USER_CACHE:
                self._evict_oldest_users()
        else:
            # Store None-marker so we don't re-query DB for non-existent users
            self._user_cache[key] = _UserCacheEntry(
                {"_exists": False, "user_id": user_id, "guild_id": guild_id},
                new_user=True,
            )
            return None

        return data

    async def update_user_xp(
        self,
        user_id: int,
        guild_id: int,
        xp: int,
        level: int,
        messages: int,
        last_message_time: float,
    ) -> None:
        """Update XP in cache (dirty-write, no immediate DB call)."""
        key = (guild_id, user_id)
        async with self._get_user_lock(guild_id, user_id):
            entry = self._user_cache.get(key)
            if entry is not None:
                entry.data["xp"] = xp
                entry.data["level"] = level
                entry.data["messages"] = messages
                entry.data["last_message_time"] = last_message_time
                entry.dirty = True
            else:
                self._user_cache[key] = _UserCacheEntry(
                    {
                        "user_id": user_id,
                        "guild_id": guild_id,
                        "xp": xp,
                        "level": level,
                        "messages": messages,
                        "last_message_time": last_message_time,
                    },
                    new_user=True,
                )
                self._user_cache[key].dirty = True

    async def insert_xp_log(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        source: str,
        reason: str = "",
    ) -> None:
        """Buffer an XP log entry (no immediate DB call)."""
        self._pending_xp_logs.append((guild_id, user_id, amount, source, reason))

    # ── Guild config cache ──────────────────────────────────────────

    async def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        """Get guild XP settings with defaults, using cache."""
        entry = self._guild_cache.get(guild_id)

        if entry is not None:
            age = time.time() - entry.loaded_at
            if age < self.GUILD_CONFIG_TTL:
                self.metrics.guild_cache_hits += 1
                return entry.data
            self.metrics.guild_cache_misses += 1
        else:
            self.metrics.guild_cache_misses += 1

        # Fetch from database
        try:
            settings = await db.get_guild_settings(guild_id)
        except Exception:
            logger.exception("Failed to fetch guild settings from DB (guild=%s)", guild_id)
            self.metrics.db_errors += 1
            if entry is not None:
                return entry.data
            settings = None

        config = {
            "xp_enabled": settings.get("xp_enabled", True) if settings else True,
            "min_xp": settings.get("min_xp", 15) if settings else 15,
            "max_xp": settings.get("max_xp", 25) if settings else 25,
            "cooldown_seconds": settings.get("cooldown_seconds", 60) if settings else 60,
            "levelup_channel_id": settings.get("levelup_channel_id") if settings else None,
        }

        self._guild_cache[guild_id] = _GuildConfigEntry(config)

        if len(self._guild_cache) > self.MAX_GUILD_CACHE:
            self._evict_oldest_guilds()

        return config

    # ── Cache invalidation ──────────────────────────────────────────

    def invalidate_user(self, user_id: int, guild_id: int) -> None:
        """Remove a user from cache (call after admin mutations)."""
        self._user_cache.pop((guild_id, user_id), None)

    def invalidate_guild_config(self, guild_id: int) -> None:
        """Remove guild config from cache (call after settings changes)."""
        self._guild_cache.pop(guild_id, None)

    def clear_all(self) -> None:
        """Clear entire cache (e.g., after full guild reset)."""
        self._user_cache.clear()
        self._guild_cache.clear()

    # ── Flush (write to DB) ────────────────────────────────────────

    async def flush_all(self) -> None:
        """Flush all dirty user data, guild configs, and buffered XP logs."""
        await self._flush_dirty_users()
        await self._flush_dirty_guild_settings()
        await self._flush_pending_xp_logs()

    # ── Background flush task ───────────────────────────────────────

    async def _flush_loop(self) -> None:
        """Periodically flush dirty data to PostgreSQL."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await asyncio.sleep(self._flush_interval)

            # Respect exponential backoff
            if time.time() < self._backoff_until:
                continue

            try:
                await self.flush_all()
                self.metrics.log_if_due(len(self._user_cache))
            except Exception:
                self._record_error()

    def _record_error(self) -> None:
        """Record a DB error and apply exponential backoff."""
        self.metrics.db_errors += 1
        self._consecutive_errors += 1
        self.metrics.retry_attempts = self._consecutive_errors

        if self._consecutive_errors >= 3:
            backoff = min(60, 2 ** self._consecutive_errors)
            self._backoff_until = time.time() + backoff
            if self._consecutive_errors % 5 == 0:
                logger.warning(
                    "LevelingCache: %d consecutive DB errors, backing off for %ds",
                    self._consecutive_errors,
                    backoff,
                )
        else:
            logger.debug("LevelingCache: DB error (attempt %d)", self._consecutive_errors)

    def _reset_backoff(self) -> None:
        """Reset error counter after a successful flush."""
        if self._consecutive_errors > 0:
            logger.info(
                "LevelingCache: DB recovered after %d errors",
                self._consecutive_errors,
            )
        self._consecutive_errors = 0
        self._backoff_until = 0.0

    # ── Dirty user flush ────────────────────────────────────────────

    async def _flush_dirty_users(self) -> None:
        """Batch-write all dirty user entries to PostgreSQL."""
        # Snapshot dirty entries under their individual locks (fast)
        dirty: List[Tuple[int, _UserCacheEntry]] = []
        async with self._user_locks_lock:
            keys = list(self._user_cache.keys())

        for key in keys:
            entry = self._user_cache.get(key)
            if entry is not None and entry.dirty:
                async with self._get_user_lock(key[0], key[1]):
                    if entry.dirty:
                        dirty.append((key, entry))
                        entry.dirty = False  # optimistically clear

        if not dirty:
            return

        self.metrics.pending_updates = len(dirty)
        logger.debug("Flushing %d dirty user entries", len(dirty))

        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                new_entries = []
                existing_entries = []
                for key, entry in dirty:
                    if entry.new_user:
                        new_entries.append((key, entry))
                    else:
                        existing_entries.append((key, entry))

                if new_entries:
                    await self._batch_insert_users(conn, new_entries)
                if existing_entries:
                    await self._batch_update_users(conn, existing_entries)

            self.metrics.db_user_writes += len(dirty)
            self._reset_backoff()

            # Mark flushed entries as no longer new
            for key, entry in dirty:
                entry.new_user = False

        except Exception:
            self._record_error()
            # Re-mark as dirty so we retry next flush
            for key, entry in dirty:
                entry.dirty = True
            logger.exception("Failed to flush %d user entries", len(dirty))

    async def _batch_insert_users(
        self,
        conn,
        entries: List[Tuple[Tuple[int, int], _UserCacheEntry]],
    ) -> None:
        """Batch INSERT new users using a single executemany."""
        if not entries:
            return
        records = []
        for (guild_id, user_id), entry in entries:
            d = entry.data
            records.append((
                user_id,
                guild_id,
                d.get("xp", 0),
                d.get("level", 0),
                d.get("messages", 0),
                d.get("last_message_time", 0),
            ))
        await conn.executemany(
            """
            INSERT INTO user_levels
                (user_id, guild_id, xp, level, messages, last_message_time, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                xp = EXCLUDED.xp,
                level = EXCLUDED.level,
                messages = EXCLUDED.messages,
                last_message_time = EXCLUDED.last_message_time,
                updated_at = NOW()
            """,
            records,
        )

    async def _batch_update_users(
        self,
        conn,
        entries: List[Tuple[Tuple[int, int], _UserCacheEntry]],
    ) -> None:
        """Batch UPDATE existing users using a single executemany."""
        if not entries:
            return
        records = []
        for (guild_id, user_id), entry in entries:
            d = entry.data
            records.append((
                d.get("xp", 0),
                d.get("level", 0),
                d.get("messages", 0),
                d.get("last_message_time", 0),
                user_id,
                guild_id,
            ))
        await conn.executemany(
            """
            UPDATE user_levels
            SET xp = $1, level = $2, messages = $3,
                last_message_time = $4, updated_at = NOW()
            WHERE user_id = $5 AND guild_id = $6
            """,
            records,
        )

    # ── Dirty guild settings flush ──────────────────────────────────

    async def _flush_dirty_guild_settings(self) -> None:
        """Write guild configs that were modified (currently unused placeholder).

        Guild settings are mostly read-only; this handles any future
        write-through needs and ensures consistency.
        """
        pass  # Guild settings are written directly by admin commands

    # ── XP log flush ────────────────────────────────────────────────

    async def _flush_pending_xp_logs(self) -> None:
        """Batch-flush buffered XP log entries."""
        if not self._pending_xp_logs:
            return

        logs = self._pending_xp_logs[:]
        self._pending_xp_logs.clear()

        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                records = [
                    (g, u, a, s, r if r else None)
                    for g, u, a, s, r in logs
                ]
                await conn.executemany(
                    """
                    INSERT INTO xp_log (guild_id, user_id, amount, source, reason)
                    VALUES ($1, $2, $3, $4, NULLIF($5, ''))
                    """,
                    records,
                )

            self.metrics.db_xp_logs_flushed += len(logs)
            self._reset_backoff()

        except Exception:
            self._record_error()
            # Re-queue logs for retry
            self._pending_xp_logs.extend(logs)
            logger.exception("Failed to flush %d XP log entries", len(logs))

    # ── Eviction ────────────────────────────────────────────────────

    def _evict_oldest_users(self) -> None:
        """Evict oldest entries when cache exceeds max size."""
        if len(self._user_cache) <= self.MAX_USER_CACHE:
            return
        # Remove dirty entries last (data loss risk)
        evictable = [
            (k, e) for k, e in self._user_cache.items() if not e.dirty
        ]
        evictable.sort(key=lambda x: x[1].loaded_at)
        excess = len(self._user_cache) - self.MAX_USER_CACHE
        for key, _ in evictable[:excess]:
            self._user_cache.pop(key, None)

    def _evict_oldest_guilds(self) -> None:
        """Evict oldest guild config entries when cache exceeds max size."""
        if len(self._guild_cache) <= self.MAX_GUILD_CACHE:
            return
        sorted_entries = sorted(
            self._guild_cache.items(), key=lambda x: x[1].loaded_at
        )
        excess = len(self._guild_cache) - self.MAX_GUILD_CACHE
        for key, _ in sorted_entries[:excess]:
            self._guild_cache.pop(key, None)

    # ── Observability ───────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Return a snapshot of cache metrics."""
        return self.metrics.snapshot(len(self._user_cache))

    @property
    def pending_log_count(self) -> int:
        return len(self._pending_xp_logs)
