"""
Quest System Cog — daily and weekly quests to engage users.

How it works:
- Quests are generated per-guild with configurable rewards
- Daily quests reset every 24 hours
- Weekly quests reset every Monday
- Users can track their progress via /quests command
- Completing quests awards bonus XP

Quest Types:
- "send_messages" — Send N messages
- "earn_xp" — Earn N XP
- "voice_hours" — Spend N hours in voice
- "level_up" — Level up N times
- "use_commands" — Use N commands
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from services.level_service import LevelService, XpSource

logger = logging.getLogger("miku.quests")

# ──────────────────────────────────────────────────────────────────────
# Quest Definitions
# ──────────────────────────────────────────────────────────────────────

QUEST_TEMPLATES = [
    {
        "type": "send_messages",
        "name": "Chatter",
        "description": "Send {amount} messages in any channel",
        "icon": "\U0001F4AC",
        "amount": 10,
        "xp_reward": 50,
    },
    {
        "type": "send_messages",
        "name": "Social Butterfly",
        "description": "Send {amount} messages in any channel",
        "icon": "\U0001F5E8",
        "amount": 25,
        "xp_reward": 100,
    },
    {
        "type": "earn_xp",
        "name": "XP Grinder",
        "description": "Earn {amount} XP from messages",
        "icon": "\u26A1",
        "amount": 200,
        "xp_reward": 150,
    },
    {
        "type": "earn_xp",
        "name": "XP Collector",
        "description": "Earn {amount} XP from messages",
        "icon": "\U0001F4B0",
        "amount": 500,
        "xp_reward": 300,
    },
    {
        "type": "voice_hours",
        "name": "Voice Chat",
        "description": "Spend {amount} minutes in voice chat",
        "icon": "\U0001F50A",
        "amount": 30,
        "xp_reward": 200,
    },
    {
        "type": "voice_hours",
        "name": "Voice Veteran",
        "description": "Spend {amount} minutes in voice chat",
        "icon": "\U0001F399",
        "amount": 60,
        "xp_reward": 400,
    },
    {
        "type": "level_up",
        "name": "Level Up!",
        "description": "Level up {amount} times",
        "icon": "\u2B50",
        "amount": 1,
        "xp_reward": 500,
    },
    {
        "type": "level_up",
        "name": "Rising Star",
        "description": "Level up {amount} times",
        "icon": "\U0001F31F",
        "amount": 3,
        "xp_reward": 1000,
    },
]


class Quest:
    """A quest instance for a user."""

    def __init__(self, template: dict, period: str = "daily"):
        self.type = template["type"]
        self.name = template["name"]
        self.description = template["description"].format(amount=template["amount"])
        self.icon = template["icon"]
        self.target_amount = template["amount"]
        self.xp_reward = template["xp_reward"]
        self.period = period  # "daily" or "weekly"
        self.progress = 0

    @property
    def is_complete(self) -> bool:
        return self.progress >= self.target_amount

    @property
    def progress_pct(self) -> float:
        return min(100.0, (self.progress / self.target_amount) * 100)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "target_amount": self.target_amount,
            "xp_reward": self.xp_reward,
            "period": self.period,
            "progress": self.progress,
            "is_complete": self.is_complete,
            "progress_pct": self.progress_pct,
        }


# ──────────────────────────────────────────────────────────────────────
# Cog
# ──────────────────────────────────────────────────────────────────────


class Quests(commands.Cog):
    """Daily and weekly quest system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = LevelService(bot)
        self._user_quests: Dict[str, List[Quest]] = {}  # key: "{guild_id}:{user_id}:{period}"

    async def cog_load(self) -> None:
        """Ensure quest tracking table exists."""
        from src.utils import database as db

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS quest_progress (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    quest_type VARCHAR(32) NOT NULL,
                    quest_name VARCHAR(64) NOT NULL,
                    period VARCHAR(16) NOT NULL,
                    progress INTEGER DEFAULT 0,
                    completed BOOLEAN DEFAULT FALSE,
                    claimed BOOLEAN DEFAULT FALSE,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (guild_id, user_id, quest_type, period, quest_name)
                )
            """)
        logger.info("Quests cog loaded")

    def _get_random_quests(self, count: int = 3, period: str = "daily") -> List[Quest]:
        """Select random quests for a user."""
        templates = random.sample(QUEST_TEMPLATES, min(count, len(QUEST_TEMPLATES)))
        return [Quest(t, period) for t in templates]

    def _get_period_end(self, period: str) -> datetime:
        """Get the expiry timestamp for a quest period."""
        now = datetime.now(timezone.utc)
        if period == "daily":
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "weekly":
            # Next Monday
            days_ahead = 7 - now.weekday()
            if days_ahead <= 0:
                days_ahead = 7
            return (now + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        return now + timedelta(days=1)

    async def _load_quests(self, guild_id: int, user_id: int, period: str) -> List[Quest]:
        """Load a user's quests from the database."""
        from src.utils import database as db

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT quest_type, quest_name, progress, completed, claimed, expires_at "
                "FROM quest_progress "
                "WHERE guild_id = $1 AND user_id = $2 AND period = $3 AND claimed = FALSE "
                "ORDER BY quest_type",
                guild_id, user_id, period,
            )

        quests = []
        now = datetime.now(timezone.utc)
        for row in rows:
            if row["expires_at"].replace(tzinfo=timezone.utc) < now:
                continue
            q = Quest({"type": row["quest_type"], "name": row["quest_name"],
                       "description": "", "icon": "", "amount": 0, "xp_reward": 0}, period)
            q.progress = row["progress"]
            # We need to match the template to fill in details
            template = next((t for t in QUEST_TEMPLATES if t["type"] == row["quest_type"]
                           and t["name"] == row["quest_name"]), None)
            if template:
                q.__init__(template, period)
                q.progress = row["progress"]
            else:
                quests.append(q)

        return quests

    async def _save_quest(self, guild_id: int, user_id: int, quest: Quest) -> None:
        """Save a quest's progress to the database."""
        from src.utils import database as db

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO quest_progress (guild_id, user_id, quest_type, quest_name, period,
                    progress, completed, claimed, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8)
                ON CONFLICT (guild_id, user_id, quest_type, period, quest_name)
                DO UPDATE SET progress = EXCLUDED.progress, completed = EXCLUDED.completed
                """,
                guild_id, user_id, quest.type, quest.name, quest.period,
                quest.progress, quest.is_complete, self._get_period_end(quest.period),
            )

    async def _ensure_quests(self, guild_id: int, user_id: int) -> None:
        """Ensure a user has active daily and weekly quests."""
        daily_key = f"{guild_id}:{user_id}:daily"
        if daily_key not in self._user_quests or not self._user_quests[daily_key]:
            daily_quests = self._get_random_quests(3, "daily")
            self._user_quests[daily_key] = daily_quests
            for q in daily_quests:
                await self._save_quest(guild_id, user_id, q)
            logger.debug("Assigned daily quests for user %s in guild %s", user_id, guild_id)

        weekly_key = f"{guild_id}:{user_id}:weekly"
        if weekly_key not in self._user_quests or not self._user_quests[weekly_key]:
            weekly_quests = self._get_random_quests(2, "weekly")
            self._user_quests[weekly_key] = weekly_quests
            for q in weekly_quests:
                await self._save_quest(guild_id, user_id, q)
            logger.debug("Assigned weekly quests for user %s in guild %s", user_id, guild_id)

    async def _track_progress(self, guild_id: int, user_id: int, quest_type: str, amount: int = 1) -> None:
        """Track quest progress for a user."""
        await self._ensure_quests(guild_id, user_id)

        for key_prefix, period in [("daily", "daily"), ("weekly", "weekly")]:
            key = f"{guild_id}:{user_id}:{period}"
            quests = self._user_quests.get(key, [])
            for quest in quests:
                if quest.type == quest_type and not quest.is_complete:
                    quest.progress += amount
                    await self._save_quest(guild_id, user_id, quest)

                    if quest.is_complete:
                        logger.info(
                            "Quest completed: user=%s guild=%s quest=%s period=%s",
                            user_id, guild_id, quest.name, period,
                        )

    async def _claim_quest(self, guild_id: int, user_id: int, quest: Quest) -> bool:
        """Claim a completed quest's reward."""
        if not quest.is_complete:
            return False

        from src.utils import database as db

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE quest_progress SET claimed = TRUE "
                "WHERE guild_id = $1 AND user_id = $2 AND quest_type = $3 AND quest_name = $4 AND period = $5",
                guild_id, user_id, quest.type, quest.name, quest.period,
            )

        # Award XP
        user_data = await db.get_user_data(user_id, guild_id)
        current_xp = user_data["xp"] if user_data else 0
        current_level = user_data["level"] if user_data else 0
        messages = user_data["messages"] if user_data else 0
        new_xp = current_xp + quest.xp_reward
        new_level = self.service.calculate_level(new_xp, guild_id)
        await db.update_user_xp(user_id, guild_id, new_xp, new_level, messages, 0)
        await db.insert_xp_log(guild_id, user_id, quest.xp_reward, XpSource.EVENT, f"Quest: {quest.name}")

        return True

    # ── Commands ─────────────────────────────────────────────────

    @commands.hybrid_command(
        name="quests",
        aliases=["q", "missions"],
        description="View your active daily and weekly quests",
    )
    @commands.guild_only()
    async def quests_command(self, ctx: commands.Context):
        """Show active quests and their progress."""
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            return

        await ctx.defer(ephemeral=True)
        await self._ensure_quests(ctx.guild.id, ctx.author.id)

        embed = discord.Embed(
            title=f"\U0001F3AF {ctx.author.display_name}'s Quests",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        for period in ["daily", "weekly"]:
            key = f"{ctx.guild.id}:{ctx.author.id}:{period}"
            quests = self._user_quests.get(key, [])

            if not quests:
                continue

            lines = []
            for quest in quests:
                status = "\u2705" if quest.is_complete else f"[{quest.progress}/{quest.target_amount}]"
                progress_bar = self._progress_bar(quest.progress_pct)
                lines.append(
                    f"{quest.icon} **{quest.name}**\n"
                    f"{progress_bar} {status} — {quest.description}\n"
                    f"Reward: {quest.xp_reward} XP"
                )

            embed.add_field(
                name=f"\U0001F4C5 {'Daily' if period == 'daily' else 'Weekly'} Quests",
                value="\n".join(lines) if lines else "No quests available.",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="claim",
        description="Claim rewards for completed quests",
    )
    @commands.guild_only()
    @app_commands.describe(quest_name="The name of the quest to claim (or 'all')")
    async def claim_command(self, ctx: commands.Context, quest_name: str = "all"):
        """Claim completed quest rewards."""
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            return

        await ctx.defer(ephemeral=True)
        await self._ensure_quests(ctx.guild.id, ctx.author.id)

        claimed = 0
        total_xp = 0

        for period in ["daily", "weekly"]:
            key = f"{ctx.guild.id}:{ctx.author.id}:{period}"
            quests = self._user_quests.get(key, [])

            for quest in quests:
                if not quest.is_complete:
                    continue
                if quest_name != "all" and quest.name.lower() != quest_name.lower():
                    continue

                if await self._claim_quest(ctx.guild.id, ctx.author.id, quest):
                    claimed += 1
                    total_xp += quest.xp_reward

        if claimed == 0:
            await ctx.send("No completed quests to claim!", ephemeral=True)
            return

        embed = discord.Embed(
            title="\u2705 Quests Claimed!",
            description=f"Claimed **{claimed}** quest{'' if claimed == 1 else 's'} for **{total_xp}** bonus XP!",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        await ctx.send(embed=embed)

    def _progress_bar(self, pct: float, length: int = 10) -> str:
        """Render a text progress bar."""
        filled = int((pct / 100) * length)
        return "\u2588" * filled + "\u2591" * (length - filled)

    # ── Tracking listeners ───────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Track message quest progress."""
        if message.author.bot or not message.guild:
            return
        await self._track_progress(message.guild.id, message.author.id, "send_messages")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Track voice quest progress."""
        if member.bot:
            return
        if after.channel and before.channel is None:
            # Joined voice — we'll track duration via the voice_xp cog
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Quests(bot))
