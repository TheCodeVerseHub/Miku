"""LevelService — single entry point for all XP/leveling business logic.

Every XP-changing action (message listener, slash commands, prefix commands,
dashboard API, admin actions, future voice/event XP) must go through this
service.  No duplicated reward logic, no scattered formula copies.

High-level responsibilities:
- XP calculation & formula management
- Cooldown tracking
- Multiplier resolution (role / channel / category)
- Restriction evaluation (ignore role, allow channel, …)
- Level-up detection & role reward assignment
- Admin XP mutation (set level, add/remove XP, reset)
- Audit logging for all admin changes
- XP log for analytics/time-series
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import discord
from discord.ext import commands

from services.formula_registry import FormulaRegistry
from utils import database as db

logger = logging.getLogger("miku.level_service")

# ──────────────────────────────────────────────────────────────────────
# Enums / constants for restriction types and XP sources
# ──────────────────────────────────────────────────────────────────────


class RestrictionType:
    IGNORE_ROLE = "IGNORE_ROLE"
    ALLOW_CHANNEL = "ALLOW_CHANNEL"
    BLOCK_CHANNEL = "BLOCK_CHANNEL"
    IGNORE_CATEGORY = "IGNORE_CATEGORY"
    ALLOW_CATEGORY = "ALLOW_CATEGORY"


_VALID_RESTRICTIONS = {
    RestrictionType.IGNORE_ROLE,
    RestrictionType.ALLOW_CHANNEL,
    RestrictionType.BLOCK_CHANNEL,
    RestrictionType.IGNORE_CATEGORY,
    RestrictionType.ALLOW_CATEGORY,
}


class XpSource:
    MESSAGE = "MESSAGE"
    VOICE = "VOICE"
    ADMIN = "ADMIN"
    BOOSTER = "BOOSTER"
    EVENT = "EVENT"
    IMPORT = "IMPORT"
    BONUS = "BONUS"


class TargetType:
    ROLE = "ROLE"
    CHANNEL = "CHANNEL"
    CATEGORY = "CATEGORY"


# ──────────────────────────────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────────────────────────────


class LevelService:
    """Central service for XP/leveling operations."""

    def __init__(
        self, bot: commands.Bot, formula_registry: FormulaRegistry | None = None
    ) -> None:
        self.bot = bot
        self.formula_registry = formula_registry or FormulaRegistry()
        self.formula_registry.load_defaults()
        # In-memory cooldown tracking (cleared on bot restart).
        self._cooldowns: dict[str, float] = {}

    # ══════════════════════════════════════════════════════════════════
    # Formula helpers (delegated to current formula)
    # ══════════════════════════════════════════════════════════════════

    def _get_formula(self, guild_id: int):
        """Resolve the formula configured for this guild (default: quadratic)."""
        # TODO: read `xp_settings.formula_name` from DB when supported.
        return self.formula_registry.get("quadratic")

    def calculate_level(self, xp: int, guild_id: int = 0) -> int:
        return self._get_formula(guild_id).calculate_level(xp)

    def calculate_xp_for_level(self, level: int, guild_id: int = 0) -> int:
        return self._get_formula(guild_id).xp_for_level(level)

    def calculate_xp_to_next_level(
        self, current_xp: int, current_level: int, guild_id: int = 0
    ) -> tuple[int, int, int]:
        return self._get_formula(guild_id).xp_to_next_level(current_xp, current_level)

    # ══════════════════════════════════════════════════════════════════
    # Cooldown
    # ══════════════════════════════════════════════════════════════════

    def is_on_cooldown(
        self, user_id: int, guild_id: int, cooldown_seconds: int = 60
    ) -> bool:
        key = f"{user_id}_{guild_id}"
        last = self._cooldowns.get(key)
        if last is None:
            return False
        return (time.time() - last) < cooldown_seconds

    def set_cooldown(self, user_id: int, guild_id: int) -> None:
        self._cooldowns[f"{user_id}_{guild_id}"] = time.time()

    # ══════════════════════════════════════════════════════════════════
    # XP gain calculation
    # ══════════════════════════════════════════════════════════════════

    async def _load_guild_config(self, guild_id: int) -> dict:
        """Load XP-related settings with defaults."""
        settings = await db.get_guild_settings(guild_id)
        return {
            "xp_enabled": settings.get("xp_enabled", True) if settings else True,
            "min_xp": settings.get("min_xp", 15) if settings else 15,
            "max_xp": settings.get("max_xp", 25) if settings else 25,
            "cooldown_seconds": (
                settings.get("cooldown_seconds", 60) if settings else 60
            ),
        }

    def _roll_base_xp(self, config: dict) -> int:
        return random.randint(config["min_xp"], config["max_xp"])

    async def _resolve_multipliers(
        self, guild_id: int, member: discord.Member, channel: discord.TextChannel
    ) -> float:
        """Compute combined multiplier for this member + channel."""
        # TODO: load from xp_multipliers table when it exists.
        # For now, always 1.0 (no multipliers).
        return 1.0

    async def _check_restrictions(
        self, guild_id: int, member: discord.Member, channel: discord.TextChannel
    ) -> bool:
        """Return True if XP should be awarded (no restriction blocks it)."""
        # TODO: load from xp_restrictions table when it exists.
        # For now, always allow.
        return True

    async def award_message_xp(self, message: discord.Message) -> dict[str, Any] | None:
        """Handle a message for XP awarding.

        Returns a dict with keys ``xp_gained``, ``old_level``, ``new_level``
        and ``leveled_up``, or ``None`` if no XP was awarded.
        """
        if message.author.bot or not message.guild:
            return None

        guild_id = message.guild.id
        user_id = message.author.id
        config = await self._load_guild_config(guild_id)

        if not config["xp_enabled"]:
            return None

        if self.is_on_cooldown(user_id, guild_id, config["cooldown_seconds"]):
            return None

        if not isinstance(message.author, discord.Member):
            return None

        if not await self._check_restrictions(
            guild_id, message.author, message.channel
        ):
            return None

        self.set_cooldown(user_id, guild_id)

        base_xp = self._roll_base_xp(config)
        multiplier = await self._resolve_multipliers(
            guild_id, message.author, message.channel
        )
        xp_gain = max(1, round(base_xp * multiplier))

        user_data = await db.get_user_data(user_id, guild_id)
        if user_data:
            current_xp = user_data["xp"]
            current_level = user_data["level"]
            messages = user_data["messages"]
        else:
            current_xp = 0
            current_level = 0
            messages = 0

        new_xp = current_xp + xp_gain
        new_level = self.calculate_level(new_xp, guild_id)
        messages += 1

        await db.update_user_xp(
            user_id, guild_id, new_xp, new_level, messages, time.time()
        )

        await self._log_xp(guild_id, user_id, xp_gain, XpSource.MESSAGE)

        leveled_up = new_level > current_level

        return {
            "xp_gained": xp_gain,
            "old_level": current_level,
            "new_level": new_level,
            "leveled_up": leveled_up,
        }

    # ══════════════════════════════════════════════════════════════════
    # Level-up handling
    # ══════════════════════════════════════════════════════════════════

    async def handle_level_up(
        self,
        guild: discord.Guild,
        member: discord.Member,
        old_level: int,
        new_level: int,
        fallback_channel: discord.abc.Messageable | None = None,
    ) -> None:
        """Post level-up announcement and assign role rewards."""
        embed = discord.Embed(
            title=" Level Up!",
            description=f"Congratulations {member.mention}! You've reached **Level {new_level}**!",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        settings = await db.get_guild_settings(guild.id)
        target_channel: discord.abc.Messageable | None = None
        used_custom_channel = False

        if settings and settings.get("levelup_channel_id"):
            ch = guild.get_channel(settings["levelup_channel_id"])
            if ch is not None and hasattr(ch, "send"):
                target_channel = ch
                used_custom_channel = True

        if target_channel is None:
            target_channel = fallback_channel

        if target_channel is None:
            return

        try:
            if not used_custom_channel:
                await target_channel.send(
                    embed=embed, delete_after=random.uniform(3, 5)
                )
            else:
                await target_channel.send(embed=embed)
        except Exception:
            if fallback_channel is not None and target_channel != fallback_channel:
                try:
                    await fallback_channel.send(
                        embed=embed, delete_after=random.uniform(3, 5)
                    )
                except Exception:
                    logger.warning(
                        "Failed to send level-up message to fallback channel in guild %s",
                        guild.id,
                    )

        for reached_level in range(old_level + 1, new_level + 1):
            await self.assign_role_reward(guild, member, reached_level)

    async def assign_role_reward(
        self, guild: discord.Guild, member: discord.Member, level: int
    ) -> None:
        """Assign a role reward for a specific level."""
        role_id = await db.get_role_for_level(guild.id, level)
        if role_id is None:
            return

        role = guild.get_role(role_id)
        if role is None:
            logger.warning(
                "Role reward target role not found (guild=%s level=%s role_id=%s)",
                guild.id,
                level,
                role_id,
            )
            return

        if role.managed:
            logger.warning(
                "Role reward role is managed (guild=%s level=%s role=%s)",
                guild.id,
                level,
                role.id,
            )
            return

        if role in member.roles:
            return

        bot_member = guild.me
        if bot_member is None and self.bot.user is not None:
            bot_member = guild.get_member(self.bot.user.id)
        if bot_member is None and self.bot.user is not None:
            try:
                bot_member = await guild.fetch_member(self.bot.user.id)
            except discord.HTTPException:
                bot_member = None
        if bot_member is None:
            return

        if not bot_member.guild_permissions.manage_roles:
            logger.warning("Missing Manage Roles (guild=%s)", guild.id)
            return
        if bot_member.top_role <= role:
            logger.warning(
                "Bot role too low for role reward (guild=%s level=%s)", guild.id, level
            )
            return

        try:
            await member.add_roles(role, reason=f"Level {level} reward")
            logger.info(
                "Assigned role reward (guild=%s user=%s level=%s role=%s)",
                guild.id,
                member.id,
                level,
                role.id,
            )
        except discord.Forbidden:
            logger.warning("Forbidden assigning role reward (guild=%s)", guild.id)
        except Exception:
            logger.exception("Failed to assign role reward (guild=%s)", guild.id)

    async def refresh_rewards(
        self, guild: discord.Guild, member: discord.Member
    ) -> None:
        """Assign any role rewards the member is missing for their current level."""
        user_data = await db.get_user_data(member.id, guild.id)
        if not user_data:
            return
        level = user_data["level"]
        rewards = await db.get_role_rewards(guild.id)
        for reward in rewards:
            if reward["level"] <= level:
                await self.assign_role_reward(guild, member, reward["level"])

    # ══════════════════════════════════════════════════════════════════
    # Admin XP mutations
    # ══════════════════════════════════════════════════════════════════

    async def set_level(
        self, guild_id: int, user_id: int, level: int, admin_id: int, reason: str = ""
    ) -> dict[str, Any]:
        """Set a user's level (recalculates XP)."""
        if level < 0:
            raise ValueError("Level must be 0 or higher")
        xp = self.calculate_xp_for_level(level, guild_id)
        user_data = await db.get_user_data(user_id, guild_id)
        old_level = user_data["level"] if user_data else 0

        await db.set_user_level(user_id, guild_id, level, xp)

        await self._log_xp(
            guild_id,
            user_id,
            xp - (user_data["xp"] if user_data else 0),
            XpSource.ADMIN,
            reason,
        )
        await self._log_audit(
            guild_id,
            user_id,
            admin_id,
            "set_level",
            {"old_level": old_level, "new_level": level, "reason": reason},
        )

        return {"old_level": old_level, "new_level": level, "xp": xp}

    async def set_xp(
        self, guild_id: int, user_id: int, xp: int, admin_id: int, reason: str = ""
    ) -> dict[str, Any]:
        """Set a user's XP directly (recalculates level)."""
        if xp < 0:
            raise ValueError("XP must be 0 or higher")
        new_level = self.calculate_level(xp, guild_id)
        user_data = await db.get_user_data(user_id, guild_id)
        messages = user_data["messages"] if user_data else 0
        old_xp = user_data["xp"] if user_data else 0
        old_level = user_data["level"] if user_data else 0

        await db.update_user_xp(user_id, guild_id, xp, new_level, messages, time.time())

        await self._log_xp(guild_id, user_id, xp - old_xp, XpSource.ADMIN, reason)
        await self._log_audit(
            guild_id,
            user_id,
            admin_id,
            "set_xp",
            {
                "old_xp": old_xp,
                "new_xp": xp,
                "old_level": old_level,
                "new_level": new_level,
                "reason": reason,
            },
        )

        return {
            "old_xp": old_xp,
            "new_xp": xp,
            "old_level": old_level,
            "new_level": new_level,
        }

    async def add_xp(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        admin_id: int,
        source: str = XpSource.ADMIN,
        reason: str = "",
    ) -> dict[str, Any]:
        """Add XP to a user."""
        user_data = await db.get_user_data(user_id, guild_id)
        if user_data:
            current_xp = user_data["xp"]
            current_level = user_data["level"]
            messages = user_data["messages"]
        else:
            current_xp = 0
            current_level = 0
            messages = 0

        new_xp = max(0, current_xp + amount)
        new_level = self.calculate_level(new_xp, guild_id)

        await db.update_user_xp(
            user_id, guild_id, new_xp, new_level, messages, time.time()
        )

        await self._log_xp(guild_id, user_id, amount, source, reason)
        if source == XpSource.ADMIN:
            await self._log_audit(
                guild_id,
                user_id,
                admin_id,
                "add_xp",
                {"amount": amount, "reason": reason},
            )

        return {
            "old_xp": current_xp,
            "new_xp": new_xp,
            "old_level": current_level,
            "new_level": new_level,
        }

    async def remove_xp(
        self, guild_id: int, user_id: int, amount: int, admin_id: int, reason: str = ""
    ) -> dict[str, Any]:
        """Remove XP from a user."""
        return await self.add_xp(
            guild_id, user_id, -amount, admin_id, XpSource.ADMIN, reason
        )

    async def reset_member(
        self, guild_id: int, user_id: int, admin_id: int, reason: str = ""
    ) -> None:
        """Reset a user's XP data entirely."""
        await db.reset_user_data(user_id, guild_id)
        await self._log_audit(
            guild_id, user_id, admin_id, "reset_member", {"reason": reason}
        )

    async def reset_guild(self, guild_id: int, admin_id: int, reason: str = "") -> None:
        """Reset all XP data for a guild."""
        await db.reset_guild_data(guild_id)
        await self._log_audit(guild_id, 0, admin_id, "reset_guild", {"reason": reason})

    # ══════════════════════════════════════════════════════════════════
    # Logging
    # ══════════════════════════════════════════════════════════════════

    async def _log_xp(
        self, guild_id: int, user_id: int, amount: int, source: str, reason: str = ""
    ) -> None:
        """Record an XP change in the xp_log."""
        try:
            await db.insert_xp_log(guild_id, user_id, amount, source, reason)
        except Exception:
            logger.exception("Failed to log XP entry")

    async def _log_audit(
        self, guild_id: int, user_id: int, admin_id: int, action: str, details: dict
    ) -> None:
        """Record an admin action in the audit log."""
        try:
            await db.insert_audit_log(guild_id, user_id, admin_id, action, details)
        except Exception:
            logger.exception("Failed to log audit entry")

    # ══════════════════════════════════════════════════════════════════
    # Queries for dashboard / analytics
    # ══════════════════════════════════════════════════════════════════

    async def get_member_stats(
        self, guild_id: int, user_id: int
    ) -> dict[str, Any] | None:
        user_data = await db.get_user_data(user_id, guild_id)
        if not user_data:
            return None
        rank = await db.get_user_rank(user_id, guild_id)
        xp = user_data["xp"]
        level = user_data["level"]
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(
            xp, level, guild_id
        )
        return {
            "xp": xp,
            "level": level,
            "messages": user_data["messages"],
            "rank": rank or 0,
            "xp_to_next_level": xp_needed,
            "xp_progress": xp_progress,
            "xp_required_for_level": xp_required,
            "progress_pct": round(
                (xp_progress / xp_required * 100) if xp_required > 0 else 0, 1
            ),
        }

    async def get_leaderboard(
        self, guild_id: int, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        return await db.get_leaderboard(guild_id, limit, offset)

    async def get_guild_stats(self, guild_id: int) -> dict[str, Any]:
        total_users = await db.get_total_users(guild_id)
        leaderboard = await db.get_leaderboard(guild_id, limit=5)
        return {
            "total_users": total_users,
            "top_users": leaderboard,
        }
