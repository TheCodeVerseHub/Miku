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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

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

    def to_dict(self) -> Dict[str, Any]:
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
ACHIEVEMENTS: List[Achievement] = [
    # ── Level Achievements ──
    Achievement("level_5", "Getting Started", "Reach Level 5", "\u2B50", "Leveling", "level", 5, 50),
    Achievement("level_10", "Getting Serious", "Reach Level 10", "\U0001F31F", "Leveling", "level", 10, 100),
    Achievement("level_25", "Dedicated", "Reach Level 25", "\U0001F3AF", "Leveling", "level", 25, 250),
    Achievement("level_50", "Halfway There", "Reach Level 50", "\U0001F451", "Leveling", "level", 50, 500),
    Achievement("level_100", "Centurion", "Reach Level 100", "\U0001F3C6", "Leveling", "level", 100, 1000),
    Achievement("level_200", "Legendary", "Reach Level 200", "\U0001F3C5", "Leveling", "level", 200, 2000),

    # ── Message Achievements ──
    Achievement("msg_100", "Chatter", "Send 100 messages", "\U0001F4AC", "Activity", "messages", 100, 10),
    Achievement("msg_500", "Talkative", "Send 500 messages", "\U0001F4AD", "Activity", "messages", 500, 50),
    Achievement("msg_1000", "Conversationalist", "Send 1,000 messages", "\U0001F5E8", "Activity", "messages", 1000, 100),
    Achievement("msg_5000", "Chat Monster", "Send 5,000 messages", "\U0001F4E3", "Activity", "messages", 5000, 500),
    Achievement("msg_10000", "Chat Lord", "Send 10,000 messages", "\U0001F3A4", "Activity", "messages", 10000, 1000),

    # ── Voice Achievements ──
    Achievement("voice_1h", "First Call", "Spend 1 hour in voice chat", "\U0001F50A", "Voice", "voice_hours", 1, 20),
    Achievement("voice_10h", "Regular Caller", "Spend 10 hours in voice chat", "\U0001F50B", "Voice", "voice_hours", 10, 100),
    Achievement("voice_50h", "Voice Veteran", "Spend 50 hours in voice chat", "\U0001F3A7", "Voice", "voice_hours", 50, 500),
    Achievement("voice_100h", "Voice Overlord", "Spend 100 hours in voice chat", "\U0001F399", "Voice", "voice_hours", 100, 1000),

    # ── XP Achievements ──
    Achievement("xp_10k", "XP Apprentice", "Accumulate 10,000 XP", "\U0001F4B0", "Wealth", "total_xp", 10000, 50),
    Achievement("xp_50k", "XP Master", "Accumulate 50,000 XP", "\U0001F4B8", "Wealth", "total_xp", 50000, 200),
    Achievement("xp_100k", "XP Millionaire", "Accumulate 100,000 XP", "\U0001F4B5", "Wealth", "total_xp", 100000, 500),
    Achievement("xp_500k", "XP Tycoon", "Accumulate 500,000 XP", "\U0001F48E", "Wealth", "total_xp", 500000, 2000),
]


# ──────────────────────────────────────────────────────────────────────
# Cog
# ──────────────────────────────────────────────────────────────────────


class Achievements(commands.Cog):
    """Achievement system — earn badges and rewards for milestones."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._all_achievements = {a.id: a for a in ACHIEVEMENTS}

    async def cog_load(self) -> None:
        """Ensure achievements table exists."""
        from utils import database as db

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

    async def check_achievements(
        self, guild_id: int, user_id: int, stats: Dict[str, Any]
    ) -> List[Achievement]:
        """Check a user's stats against all achievements and unlock new ones."""
        from utils import database as db

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Get already unlocked achievements for this user
            unlocked_rows = await conn.fetch(
                "SELECT achievement_id FROM user_achievements WHERE guild_id = $1 AND user_id = $2",
                guild_id, user_id,
            )
            unlocked_ids = {r["achievement_id"] for r in unlocked_rows}

            newly_unlocked: List[Achievement] = []

            for achievement in ACHIEVEMENTS:
                if achievement.id in unlocked_ids:
                    continue

                # Check if the threshold is met
                stat_value = stats.get(achievement.check, 0)
                if stat_value >= achievement.threshold:
                    # Unlock the achievement
                    await conn.execute(
                        """
                        INSERT INTO user_achievements (guild_id, user_id, achievement_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT DO NOTHING
                        """,
                        guild_id, user_id, achievement.id,
                    )
                    newly_unlocked.append(achievement)

                    # Award XP reward if any
                    if achievement.xp_reward > 0:
                        try:
                            await db.insert_xp_log(
                                guild_id, user_id,
                                achievement.xp_reward,
                                "ACHIEVEMENT",
                                f"Achievement: {achievement.name}",
                            )
                        except Exception:
                            logger.exception("Failed to log XP reward for achievement")

            return newly_unlocked

    @commands.hybrid_command(
        name="achievements",
        aliases=["ach", "badges"],
        description="View your unlocked achievements",
    )
    @commands.guild_only()
    async def achievements_command(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ):
        """Display a user's achievements."""
        if ctx.guild is None:
            return
        target = member or ctx.author
        if target.bot:
            await ctx.send("Bots don't have achievements!", ephemeral=True)
            return

        from utils import database as db

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT achievement_id, unlocked_at FROM user_achievements "
                "WHERE guild_id = $1 AND user_id = $2 ORDER BY unlocked_at",
                ctx.guild.id, target.id,
            )

        unlocked = {r["achievement_id"] for r in rows}

        embed = discord.Embed(
            title=f"\U0001F3C6 {target.display_name}'s Achievements",
            description=f"**{len(unlocked)}** / **{len(ACHIEVEMENTS)}** achievements unlocked",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Group by category
        categories: Dict[str, List[Achievement]] = {}
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
