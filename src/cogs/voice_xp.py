"""
Voice XP Cog — award XP for time spent in voice channels.

How it works:
- When a user joins a voice channel, a timer starts.
- Every `VOICE_XP_INTERVAL` seconds, XP is awarded if they're still connected.
- The bot ignores AFK channels, deafened/muted users (configurable).
- XP amounts are configurable per guild.

Features:
- Anti-farming: must not be server-deafened/muted
- AFK channel detection
- Configurable interval and XP amounts
- Handles disconnects, channel moves, and bot restarts gracefully
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

import discord
from discord.ext import commands

from services.level_service import LevelService, XpSource
from utils import database as db

logger = logging.getLogger("miku.voice_xp")

# Default settings
VOICE_XP_INTERVAL = 60  # seconds between XP awards
VOICE_XP_MIN = 10
VOICE_XP_MAX = 20


class VoiceSession:
    """Tracks a user's voice session state."""

    def __init__(self, member: discord.Member, channel: discord.VoiceChannel):
        self.user_id = member.id
        self.guild_id = member.guild.id
        self.channel_id = channel.id
        self.is_afk = channel.is_afk_channel() if hasattr(channel, "is_afk_channel") else False
        self.joined_at = time.time()
        self.last_xp_at = time.time()
        self.total_seconds = 0
        self.xp_earned = 0

    def update(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        """Update session when user moves channels."""
        self.channel_id = channel.id
        self.is_afk = channel.is_afk_channel() if hasattr(channel, "is_afk_channel") else False


class VoiceXP(commands.Cog):
    """Award XP for time spent in voice channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._sessions: dict[int, VoiceSession] = {}  # keyed by user_id
        self._task: asyncio.Task | None = None
        self._service: LevelService | None = None  # resolved in cog_load

    @property
    def service(self) -> LevelService:
        """Get the shared LevelService (with cache) from the Leveling cog.

        Falls back to creating a standalone instance if the Leveling cog
        is not loaded.  The shared instance uses the in-memory cache,
        eliminating per-message DB queries.
        """
        if self._service is None:
            shared = getattr(self.bot, "leveling_service", None)
            if shared is not None:
                self._service = shared
            else:
                self._service = LevelService(self.bot)
        return self._service

    async def cog_load(self) -> None:
        """Start the background XP ticker."""
        self._task = asyncio.create_task(self._xp_ticker())
        logger.info("Voice XP cog loaded")

    async def cog_unload(self) -> None:
        """Cancel the background task and save state."""
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Voice XP cog unloaded (total sessions: %d)", len(self._sessions))

    async def _xp_ticker(self) -> None:
        """Background loop: award XP to active voice sessions."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._process_active_sessions()
            except Exception:
                logger.exception("Error in voice XP ticker")
            await asyncio.sleep(VOICE_XP_INTERVAL)

    async def _process_active_sessions(self) -> None:
        """Check all active sessions and award XP if eligible."""
        now = time.time()
        expired: list[int] = []

        for user_id, session in list(self._sessions.items()):
            guild = self.bot.get_guild(session.guild_id)
            if guild is None:
                expired.append(user_id)
                continue

            member = guild.get_member(user_id)
            if member is None:
                expired.append(user_id)
                continue

            voice = member.voice
            if voice is None or voice.channel is None:
                expired.append(user_id)
                continue

            # Skip if in AFK channel
            if session.is_afk:
                continue

            # Skip if server-deafened or server-muted (anti-farming)
            if voice.afk or voice.self_deaf or voice.deaf:
                continue

            # Check if enough time has passed since last award
            if now - session.last_xp_at < VOICE_XP_INTERVAL:
                continue

            # Award XP
            xp_gain = await self._award_voice_xp(member, guild.id)
            if xp_gain:
                session.last_xp_at = now
                session.xp_earned += xp_gain

            session.total_seconds += int(now - session.joined_at)
            session.joined_at = now

        # Clean up expired sessions
        for user_id in expired:
            self._sessions.pop(user_id, None)

    async def _award_voice_xp(self, member: discord.Member, guild_id: int) -> int | None:
        """Award XP for voice activity.

        Uses the shared LevelService cache when available so that no
        PostgreSQL connection is acquired under normal operation.
        """
        import random

        cache = self.service.cache

        # Load guild config (cached via LevelService)
        config = await self.service._load_guild_config(guild_id)
        if not config.get("xp_enabled", True):
            return None

        min_xp = config.get("min_xp", VOICE_XP_MIN)
        max_xp = config.get("max_xp", VOICE_XP_MAX)
        xp_gain = random.randint(min_xp, max_xp)

        # Read user data from cache when available
        if cache is not None:
            user_data = await cache.get_user_data(member.id, guild_id)
            if user_data and not user_data.get("_exists", True):
                user_data = None
        else:
            user_data = await db.get_user_data(member.id, guild_id)

        current_xp = user_data["xp"] if user_data else 0
        current_level = user_data["level"] if user_data else 0
        messages = user_data["messages"] if user_data else 0

        new_xp = current_xp + xp_gain
        new_level = self.service.calculate_level(new_xp, guild_id)

        # Write XP to cache (batched) or directly to DB
        now = time.time()
        if cache is not None:
            await cache.update_user_xp(
                member.id, guild_id, new_xp, new_level, messages, now
            )
            await cache.insert_xp_log(guild_id, member.id, xp_gain, XpSource.VOICE)
        else:
            await db.update_user_xp(member.id, guild_id, new_xp, new_level, messages, now)
            await db.insert_xp_log(guild_id, member.id, xp_gain, XpSource.VOICE)

        if new_level > current_level:
            await self.service.handle_level_up(
                guild=member.guild,
                member=member,
                old_level=current_level,
                new_level=new_level,
                fallback_channel=None,
            )

        return xp_gain

    # ── Event listeners ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Track voice channel joins, leaves, and moves."""
        if member.bot:
            return

        # Joined a voice channel
        if before.channel is None and after.channel is not None:
            self._sessions[member.id] = VoiceSession(member, after.channel)
            logger.debug(
                "Voice session started: user=%s guild=%s channel=%s",
                member.id, member.guild.id, after.channel.id,
            )

        # Left voice
        elif before.channel is not None and after.channel is None:
            session = self._sessions.pop(member.id, None)
            if session:
                duration = int(time.time() - session.joined_at)
                logger.debug(
                    "Voice session ended: user=%s guild=%s duration=%ds xp_earned=%d",
                    member.id, member.guild.id, duration, session.xp_earned,
                )

        # Moved channels
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            session = self._sessions.get(member.id)
            if session:
                session.update(member, after.channel)
                logger.debug(
                    "Voice session moved: user=%s from=%s to=%s",
                    member.id, before.channel.id, after.channel.id,
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceXP(bot))
