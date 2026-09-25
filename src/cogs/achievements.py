"""
Achievement System Cog — milestones, badges, and titles for users.

How it works:
- Tracks various user stats (messages, levels, voice time, reactions, etc.)
- Awards achievements when milestones are reached
- Achievements are stored per-guild and persist across restarts

Achievement Types:
- Level milestones (Level 5, 10, 25, 50, 100)
- Message milestones (100, 500, 1000, 5000, 10000 messages)
- Voice milestones (1h, 10h, 50h, 100h in voice)
- XP milestones (10k, 50k, 100k, 500k XP)
- Social (reactions received, friendships)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import discord
from cachetools import TTLCache
from discord.ext import commands

from services.level_service import LevelService, XpSource
from utils import database as db

logger = logging.getLogger("miku.achievements")


# ──────────────────────────────────────────────────────────────────────
# Achievement Definitions
# ──────────────────────────────────────────────────────────────────────


class Achievement:
    """A single achievement definition."""

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        icon: str,
        category: str,
        check: str,
        threshold: int,
        xp_reward: int = 0,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon  # Emoji icon
        self.category = category
        self.check = check  # What stat to check: "level", "messages", "voice_hours", "total_xp"
        self.threshold = threshold
        self.xp_reward = xp_reward

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "check": self.check,
            "threshold": self.threshold,
            "xp_reward": self.xp_reward,
        }


# Full list of achievements
ACHIEVEMENTS: list[Achievement] = [
    # ── Level Achievements ──
    Achievement("level_5", "Getting Started", "Reach Level 5", "\u2B50", "Leveling", "level", 5, 50),
    Achievement("level_10", "Getting Serious", "Reach Level 10", "\U0001F31F", "Leveling", "level", 10, 100),
    Achievement("level_25", "Dedicated", "Reach Level 25", "\U0001F3AF", "Leveling", "level", 25, 250),
    Achievement("level_50", "Halfway There", "Reach Level 50", "\U0001F451", "Leveling", "level", 50, 500),
    Achievement("level_100", "Centurion", "Reach Level 100", "\U0001F3C6", "Leveling", "level", 100, 1000),
    Achievement("level_200", "Legendary", "Reach Level 200", "\U0001F3C5", "Leveling", "level", 200, 2000),

    # ── Message Achievements ──
    Achievement(
        "msg_100", "Chatter", "Send 100 messages",
        "\U0001F4AC", "Activity", "messages", 100, 10,
    ),
    Achievement(
        "msg_500", "Talkative", "Send 500 messages",
        "\U0001F4AD", "Activity", "messages", 500, 50,
    ),
    Achievement(
        "msg_1000", "Conversationalist", "Send 1,000 messages",
        "\U0001F5E8", "Activity", "messages", 1000, 100,
    ),
    Achievement(
        "msg_5000", "Chat Monster", "Send 5,000 messages",
        "\U0001F4E3", "Activity", "messages", 5000, 500,
    ),
    Achievement(
        "msg_10000", "Chat Lord", "Send 10,000 messages",
        "\U0001F3A4", "Activity", "messages", 10000, 1000,
    ),

    # ── Voice Achievements ──
    Achievement(
        "voice_1h", "First Call", "Spend 1 hour in voice chat",
        "\U0001F50A", "Voice", "voice_hours", 1, 20,
    ),
    Achievement(
        "voice_10h", "Regular Caller",
        "Spend 10 hours in voice chat",
        "\U0001F50B", "Voice", "voice_hours", 10, 100,
    ),
    Achievement(
        "voice_50h", "Voice Veteran",
        "Spend 50 hours in voice chat",
        "\U0001F3A7", "Voice", "voice_hours", 50, 500,
    ),
    Achievement(
        "voice_100h", "Voice Overlord",
        "Spend 100 hours in voice chat",
        "\U0001F399", "Voice", "voice_hours", 100, 1000,
    ),

    # ── XP Achievements ──
    Achievement(
        "xp_10k", "XP Apprentice", "Accumulate 10,000 XP",
        "\U0001F4B0", "Wealth", "total_xp", 10000, 50,
    ),
    Achievement("xp_50k", "XP Master", "Accumulate 50,000 XP", "\U0001F4B8", "Wealth", "total_xp", 50000, 200),
    Achievement("xp_100k", "XP Millionaire", "Accumulate 100,000 XP", "\U0001F4B5", "Wealth", "total_xp", 100000, 500),
    Achievement("xp_500k", "XP Tycoon", "Accumulate 500,000 XP", "\U0001F48E", "Wealth", "total_xp", 500000, 2000),
]


# ──────────────────────────────────────────────────────────────────────
# Cog
# ──────────────────────────────────────────────────────────────────────


class Achievements(commands.Cog):
    """Achievement system — earn badges and rewards for milestones."""

    #: Evaluate a member at most this often (milestones are not urgent).
    CHECK_THROTTLE_SECONDS = 60
    #: How long a member's unlocked-id set stays cached.
    UNLOCKED_TTL_SECONDS = 1800

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._all_achievements = {a.id: a for a in ACHIEVEMENTS}
        self._service: LevelService | None = None
        # (guild_id, user_id) -> set of unlocked achievement ids
        self._unlocked: TTLCache = TTLCache(maxsize=5000, ttl=self.UNLOCKED_TTL_SECONDS)
        # (guild_id, user_id) -> last time this member was evaluated
        self._last_checked: TTLCache = TTLCache(maxsize=5000, ttl=self.CHECK_THROTTLE_SECONDS)

    @property
    def service(self) -> LevelService:
        """The shared cache-aware LevelService, like other XP-aware cogs use."""
        if self._service is None:
            shared = getattr(self.bot, "leveling_service", None)
            self._service = shared if shared is not None else LevelService(self.bot)
        return self._service

    async def cog_load(self) -> None:
        """Ensure achievements table exists."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    achievement_id VARCHAR(32) NOT NULL,
                    unlocked_at TIMESTAMP DEFAULT NOW(),
                    notified BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (guild_id, user_id, achievement_id)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_achievements_user
                ON user_achievements(guild_id, user_id)
            """)
        logger.info("Achievements cog loaded (%d achievements registered)", len(ACHIEVEMENTS))

    async def _load_unlocked(self, guild_id: int, user_id: int) -> set[str]:
        """Return the ids this member has unlocked, cached in memory."""
        key = (guild_id, user_id)
        cached = self._unlocked.get(key)
        if cached is not None:
            return cached

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT achievement_id FROM user_achievements WHERE guild_id = $1 AND user_id = $2",
                guild_id, user_id,
            )

        unlocked = {r["achievement_id"] for r in rows}
        self._unlocked[key] = unlocked
        return unlocked

    def _pending(self, unlocked: set[str], stats: dict[str, Any]) -> list[Achievement]:
        """Achievements whose threshold the stats now meet but which are locked."""
        return [
            achievement
            for achievement in ACHIEVEMENTS
            if achievement.id not in unlocked
            and stats.get(achievement.check, 0) >= achievement.threshold
        ]

    async def check_achievements(
        self, guild_id: int, user_id: int, stats: dict[str, Any]
    ) -> list[Achievement]:
        """Unlock any achievements the given stats qualify for and pay their XP.

        Deliberately touches the database only when something is actually being
        unlocked: the unlocked-id set is cached, and a member who is below every
        threshold returns before any query runs - this is called from the message
        path, so it has to be cheap.
        """
        unlocked = await self._load_unlocked(guild_id, user_id)
        newly_unlocked = self._pending(unlocked, stats)
        if not newly_unlocked:
            return []

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO user_achievements (guild_id, user_id, achievement_id)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                [(guild_id, user_id, achievement.id) for achievement in newly_unlocked],
            )

        unlocked.update(achievement.id for achievement in newly_unlocked)

        # Pay the reward. This used to only write an `xp_log` row, so the member
        # was told they earned XP that never reached their total.
        for achievement in newly_unlocked:
            if achievement.xp_reward > 0:
                await self._grant_reward(guild_id, user_id, achievement)

        return newly_unlocked

    async def _grant_reward(self, guild_id: int, user_id: int, achievement: Achievement) -> None:
        """Award an achievement's XP through LevelService (cache-aware + logged)."""
        try:
            await self.service.add_xp(
                guild_id,
                user_id,
                achievement.xp_reward,
                admin_id=0,
                source=XpSource.EVENT,
                reason=f"Achievement: {achievement.name}",
            )
        except Exception:
            logger.exception(
                "Failed to grant achievement reward %s to user=%s guild=%s",
                achievement.id, user_id, guild_id,
            )

    async def _collect_stats(self, guild_id: int, user_id: int) -> dict[str, int] | None:
        """Read the stats achievements are evaluated against (cache-first)."""
        data = await self.service.get_user_row(guild_id, user_id)
        if not data:
            return None
        return {
            "level": data.get("level") or 0,
            "messages": data.get("messages") or 0,
            "total_xp": data.get("xp") or 0,
            # Not persisted anywhere yet, so the voice achievements cannot unlock.
            "voice_hours": 0,
        }

    def _should_check(self, guild_id: int, user_id: int) -> bool:
        """Throttle per member so the message path stays cheap."""
        key = (guild_id, user_id)
        if key in self._last_checked:
            return False
        self._last_checked[key] = time.time()
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Unlock achievements when a member crosses a milestone."""
        if message.author.bot or message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return
        if not self._should_check(message.guild.id, message.author.id):
            return

        try:
            stats = await self._collect_stats(message.guild.id, message.author.id)
            if stats is None:
                return
            unlocked = await self.check_achievements(message.guild.id, message.author.id, stats)
        except Exception:
            logger.exception(
                "Achievement check failed (user=%s guild=%s)",
                message.author.id, message.guild.id,
            )
            return

        if unlocked:
            await self._announce(message, unlocked)

    async def _announce(self, message: discord.Message, unlocked: list[Achievement]) -> None:
        """Tell the member (and the channel) about new achievements."""
        lines = [
            f"{achievement.icon} **{achievement.name}** — {achievement.description}"
            + (f" (+{achievement.xp_reward} XP)" if achievement.xp_reward else "")
            for achievement in unlocked
        ]
        embed = discord.Embed(
            title="\U0001F3C6 Achievement Unlocked!",
            description=f"{message.author.mention}\n\n" + "\n".join(lines),
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        try:
            await message.channel.send(embed=embed)
        except Exception:
            logger.debug("Could not announce achievements in %s", message.channel)

    @commands.hybrid_command(
        name="achievements",
        aliases=["ach", "badges"],
        description="View your unlocked achievements",
    )
    @commands.guild_only()
    async def achievements_command(
        self, ctx: commands.Context, member: discord.Member | None = None
    ):
        """Display a user's achievements."""
        if ctx.guild is None:
            return
        target = member or ctx.author
        if target.bot:
            await ctx.send("Bots don't have achievements!", ephemeral=True)
            return

        unlocked = await self._load_unlocked(ctx.guild.id, target.id)

        embed = discord.Embed(
            title=f"\U0001F3C6 {target.display_name}'s Achievements",
            description=f"**{len(unlocked)}** / **{len(ACHIEVEMENTS)}** achievements unlocked",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Group by category
        categories: dict[str, list[Achievement]] = {}
        for ach in ACHIEVEMENTS:
            categories.setdefault(ach.category, []).append(ach)

        for category, achievements in categories.items():
            lines = []
            for ach in achievements:
                if ach.id in unlocked:
                    lines.append(f"{ach.icon} **{ach.name}** — {ach.description}")
                else:
                    lines.append(f"\u2B1C ~~{ach.name}~~ — {ach.description}")

            embed.add_field(
                name=f"\U0001F4CB {category}",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(
            text=f"{len(unlocked)}/{len(ACHIEVEMENTS)} unlocked"
        )
        await ctx.send(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Achievements(bot))
