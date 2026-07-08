"""Leveling Cog — XP tracking and leveling system.

Business logic is delegated to :class:`LevelService`; this cog owns only the
Discord presentation layer (commands, listeners, embed formatting).
"""

from __future__ import annotations

import logging
from io import BytesIO
import discord
from discord import app_commands
from discord.ext import commands

from services.level_service import LevelService
from utils import database as db
from utils.discord_helpers import maybe_defer, send
from utils.rank_card import RankCardGenerator

logger = logging.getLogger("miku.leveling")


class _LeaderboardView(discord.ui.View):
    """Paginated leaderboard view."""

    def __init__(
        self,
        *,
        cog: "Leveling",
        author_id: int,
        guild_id: int,
        page: int,
        per_page: int,
        timeout: float = 120,
    ):
        super().__init__(timeout=timeout)
        self._cog = cog
        self._author_id = author_id
        self._guild_id = guild_id
        self._per_page = per_page
        self.page = max(1, page)
        self.total_pages = 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None:
            return False
        if interaction.user.id != self._author_id:
            msg = "Only the user who ran the command can use these buttons."
            try:
                await interaction.response.send_message(msg, ephemeral=True)
            except discord.InteractionResponded:
                try:
                    await interaction.followup.send(msg, ephemeral=True)
                except Exception:
                    logger.debug("Failed to send ephemeral response to non-author user")
            return False
        if interaction.guild is None or interaction.guild.id != self._guild_id:
            return False
        return True

    def _sync_button_state(self) -> None:
        prev_button = getattr(self, "prev_page", None)
        next_button = getattr(self, "next_page", None)
        if prev_button is not None:
            prev_button.disabled = self.page <= 1
        if next_button is not None:
            next_button.disabled = self.page >= self.total_pages

    async def _refresh(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        embed, page, total_pages, has_data = await self._cog._build_leaderboard_embed(
            interaction.guild, page=self.page, per_page=self._per_page,
        )
        if not has_data:
            self.stop()
            for item in self.children:
                item.disabled = True
            try:
                await interaction.response.edit_message(
                    content="No one has earned any XP yet! Start chatting to level up!",
                    embed=None, view=self,
                )
            except discord.InteractionResponded:
                if interaction.message is not None:
                    await interaction.message.edit(
                        content="No one has earned any XP yet! Start chatting to level up!",
                        embed=None, view=self,
                    )
            return
        self.page = page
        self.total_pages = total_pages
        self._sync_button_state()
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.InteractionResponded:
            if interaction.message is not None:
                await interaction.message.edit(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        message = getattr(self, "message", None)
        if message is not None:
            try:
                await message.edit(view=self)
            except Exception:
                logger.debug("Failed to disable buttons on leaderboard timeout")

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(1, self.page - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages, self.page + 1)
        await self._refresh(interaction)


class Leveling(commands.Cog):
    """XP and leveling system for Discord servers."""

    EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rank_card_generator = RankCardGenerator()
        self.service = LevelService(bot)

    async def cog_load(self):
        logger.info("Leveling cog loaded")

    async def cog_unload(self):
        logger.info("Leveling cog unloaded")
        try:
            await self.rank_card_generator.close()
        except Exception:
            logger.exception("Failed to close RankCardGenerator")

    # ──────────────────────────────────────────────────────────────────
    # Formula helpers (delegated to service)
    # ──────────────────────────────────────────────────────────────────

    def calculate_level(self, xp: int, guild_id: int = 0) -> int:
        return self.service.calculate_level(xp, guild_id)

    def calculate_xp_for_level(self, level: int, guild_id: int = 0) -> int:
        return self.service.calculate_xp_for_level(level, guild_id)

    def calculate_xp_to_next_level(self, current_xp: int, current_level: int, guild_id: int = 0) -> tuple:
        return self.service.calculate_xp_to_next_level(current_xp, current_level, guild_id)

    # ──────────────────────────────────────────────────────────────────
    # Message XP listener
    # ──────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        result = await self.service.award_message_xp(message)
        if result is None:
            return
        if result["leveled_up"]:
            await self.service.handle_level_up(
                guild=message.guild,
                member=message.author,
                old_level=result["old_level"],
                new_level=result["new_level"],
                fallback_channel=message.channel,
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Remove leveling data when a member leaves the guild."""
        if member.bot:
            return
        try:
            await db.delete_user_leveling_data(member.id, member.guild.id)
            logger.info(
                "Cleaned up leveling data for departed member %s in guild %s",
                member.id, member.guild.id,
            )
        except Exception:
            logger.exception(
                "Failed to clean up leveling data for %s in guild %s",
                member.id, member.guild.id,
            )

    # ──────────────────────────────────────────────────────────────────
    # Leaderboard embed builder
    # ──────────────────────────────────────────────────────────────────

    async def _build_leaderboard_embed(
        self, guild: discord.Guild, *, page: int, per_page: int,
    ) -> tuple[discord.Embed, int, int, bool]:
        total_users = await db.get_total_users(guild.id)
        if total_users <= 0:
            embed = discord.Embed(
                title=f"\N{TROPHY} {guild.name} Leaderboard",
                description="No one has earned any XP yet! Start chatting to level up!",
                color=self.EMBED_COLOR,
            )
            embed.set_footer(text="Page 1/1 \u2022 0 total users")
            return embed, 1, 1, False

        total_pages = max(1, (total_users + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page
        lb_data = await db.get_leaderboard(guild.id, limit=per_page, offset=offset)

        embed = discord.Embed(
            title=f"\N{TROPHY} {guild.name} Leaderboard",
            color=self.EMBED_COLOR,
        )
        lines: list[str] = []
        for idx, entry in enumerate(lb_data, start=offset + 1):
            member = guild.get_member(entry["user_id"])
            display = member.display_name if member is not None else f"<@{entry['user_id']}>"
            medals = ["\U0001F947", "\U0001F948", "\U0001F949"]
            medal = medals[idx - 1] if idx <= 3 else f"`#{idx}`"
            lines.append(
                f"{medal} **{display}**\n"
                f"     Level {entry['level']} \u2022 {entry['xp']:,} XP \u2022 {entry['messages']:,} messages"
            )
        embed.description = "\n\n".join(lines) if lines else "No user data available"
        embed.set_footer(text=f"Page {page}/{total_pages} \u2022 {total_users} total users")
        return embed, page, total_pages, True

    # ──────────────────────────────────────────────────────────────────
    # User commands
    # ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="rank", aliases=["level", "lvl"], description="View your or another user's rank card")
    @commands.guild_only()
    @app_commands.describe(user="The user to check (leave empty for yourself)")
    async def rank(self, ctx: commands.Context, user: discord.Member | None = None):
        if ctx.guild is None:
            return
        target = user or ctx.author
        if target.bot:
            await send(ctx, "Bots don't have ranks!", ephemeral=True)
            return
        await maybe_defer(ctx)

        user_data = await db.get_user_data(target.id, ctx.guild.id)
        if not user_data:
            await send(ctx, f"{target.mention} hasn't earned any XP yet!")
            return

        xp = user_data["xp"]
        level = user_data["level"]
        messages = user_data["messages"]
        rank = await db.get_user_rank(target.id, ctx.guild.id)
        if rank is None:
            rank = 0
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(xp, level, ctx.guild.id)

        try:
            card_image = await self.rank_card_generator.generate_rank_card(
                avatar_url=target.display_avatar.url,
                username=target.display_name,
                rank=rank,
                level=level,
                current_xp=xp_progress,
                required_xp=xp_required,
                total_xp=xp,
                messages=messages,
                accent_color=(88, 101, 242),
            )
            if isinstance(card_image, (bytes, bytearray, memoryview)):
                file = discord.File(fp=BytesIO(bytes(card_image)), filename="rank_card.png")
            else:
                image_bytes = self.rank_card_generator.save_to_bytes(card_image)
                file = discord.File(fp=image_bytes, filename="rank_card.png")
            await send(ctx, file=file)
        except Exception as e:
            logger.error("Rank card generation failed: %s", e)
            embed = discord.Embed(title=f"\U0001F3C6 {target.display_name}'s Rank", color=self.EMBED_COLOR)
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Rank", value=f"#{rank}", inline=True)
            embed.add_field(name="Level", value=str(level), inline=True)
            embed.add_field(name="Messages", value=f"{messages:,}", inline=True)
            embed.add_field(
                name="XP Progress",
                value=f"{xp_progress:,} / {xp_required:,} ({xp_needed:,} to level {level + 1})",
                inline=False,
            )
            embed.set_footer(text=f"Total XP: {xp:,}")
            await send(ctx, embed=embed)

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="View the server leaderboard")
    @commands.guild_only()
    @app_commands.describe(page="Page number to view")
    async def leaderboard(self, ctx: commands.Context, page: int = 1):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        per_page = 10
        embed, page, total_pages, has_data = await self._build_leaderboard_embed(
            ctx.guild, page=page, per_page=per_page,
        )
        if not has_data:
            await send(ctx, "No one has earned any XP yet! Start chatting to level up!", ephemeral=True)
            return
        view = _LeaderboardView(
            cog=self, author_id=ctx.author.id, guild_id=ctx.guild.id,
            page=page, per_page=per_page,
        )
        view.total_pages = total_pages
        view._sync_button_state()
        await send(ctx, embed=embed, view=view)

    @commands.hybrid_command(name="xp", description="View detailed XP information")
    @commands.guild_only()
    @app_commands.describe(user="The user to check")
    async def xp(self, ctx: commands.Context, user: discord.Member | None = None):
        if ctx.guild is None:
            return
        target = user or ctx.author
        if target.bot:
            await send(ctx, "Bots don't have XP!", ephemeral=True)
            return
        await maybe_defer(ctx)

        user_data = await db.get_user_data(target.id, ctx.guild.id)
        if not user_data:
            await send(ctx, f"{target.mention} hasn't earned any XP yet!", ephemeral=True)
            return

        xp = user_data["xp"]
        level = user_data["level"]
        messages = user_data["messages"]
        rank = await db.get_user_rank(target.id, ctx.guild.id)
        if rank is None:
            rank = 0
        xp_needed, xp_progress, xp_required = self.calculate_xp_to_next_level(xp, level, ctx.guild.id)
        avg_xp = xp / messages if messages > 0 else 0

        embed = discord.Embed(title=f"\U0001F4CA {target.display_name}'s XP Details", color=self.EMBED_COLOR)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Server Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Total XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="Messages", value=f"{messages:,}", inline=True)
        embed.add_field(name="Avg XP/Message", value=f"{avg_xp:.1f}", inline=True)
        embed.add_field(name="XP to Level Up", value=f"{xp_needed:,}", inline=True)
        embed.add_field(
            name="Progress to Next Level",
            value=f"{xp_progress:,} / {xp_required:,} ({(xp_progress / xp_required * 100):.1f}%)",
            inline=False,
        )
        await send(ctx, embed=embed)

    # ──────────────────────────────────────────────────────────────────
    # Admin commands — Level management (all delegate to LevelService)
    # ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="setlevel", description="Set a user's level (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user="The user", level="The level to set")
    async def setlevel(self, ctx: commands.Context, user: discord.Member, level: int):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        try:
            result = await self.service.set_level(
                guild_id=ctx.guild.id,
                user_id=user.id,
                level=level,
                admin_id=ctx.author.id,
                reason=f"setlevel by {ctx.author}",
            )
        except ValueError as e:
            await send(ctx, f"\u274c {e}", ephemeral=True)
            return

        await self._ensure_refresh_rewards(ctx.guild, user)

        embed = discord.Embed(
            title="\U0001F3AF Level Set",
            description=f"Set {user.mention} to **Level {level}** ({result['xp']:,} XP)",
            color=self.EMBED_COLOR,
        )
        await send(ctx, embed=embed)

    @commands.hybrid_command(name="addxp", description="Add XP to a user (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user="The user", amount="Amount of XP to add")
    async def addxp(self, ctx: commands.Context, user: discord.Member, amount: int):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        result = await self.service.add_xp(
            guild_id=ctx.guild.id,
            user_id=user.id,
            amount=amount,
            admin_id=ctx.author.id,
            reason=f"addxp by {ctx.author}",
        )

        await self._ensure_refresh_rewards(ctx.guild, user)

        embed = discord.Embed(
            title="\u2795 XP Added",
            description=f"Added {amount:,} XP to {user.mention}\nNew Level: **{result['new_level']}** | Total XP: {result['new_xp']:,}",
            color=self.EMBED_COLOR,
        )
        await send(ctx, embed=embed)

    @commands.hybrid_command(name="removexp", description="Remove XP from a user (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user="The user", amount="Amount of XP to remove")
    async def removexp(self, ctx: commands.Context, user: discord.Member, amount: int):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        result = await self.service.remove_xp(
            guild_id=ctx.guild.id,
            user_id=user.id,
            amount=amount,
            admin_id=ctx.author.id,
            reason=f"removexp by {ctx.author}",
        )

        embed = discord.Embed(
            title="\u2796 XP Removed",
            description=f"Removed {amount:,} XP from {user.mention}\nNew Level: **{result['new_level']}** | Total XP: {result['new_xp']:,}",
            color=self.EMBED_COLOR,
        )
        await send(ctx, embed=embed)

    @commands.hybrid_command(name="resetlevel", description="Reset a user's XP data (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(user="The user to reset")
    async def resetlevel(self, ctx: commands.Context, user: discord.Member):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        await self.service.reset_member(
            guild_id=ctx.guild.id,
            user_id=user.id,
            admin_id=ctx.author.id,
            reason=f"resetlevel by {ctx.author}",
        )
        embed = discord.Embed(
            title="\U0001F504 Level Reset",
            description=f"Reset all level data for {user.mention}",
            color=self.EMBED_COLOR,
        )
        await send(ctx, embed=embed)

    @commands.hybrid_command(name="resetalllevels", description="Reset all server level data (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(confirm="Type CONFIRM to proceed")
    async def resetalllevels(self, ctx: commands.Context, confirm: str | None = None):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        if confirm != "CONFIRM":
            embed = discord.Embed(
                title="\u26a0\ufe0f Warning",
                description="This will **delete all level data** for this server!\n\n"
                f"To proceed, use: `{ctx.prefix}resetalllevels CONFIRM`",
                color=discord.Color.red(),
            )
            await send(ctx, embed=embed)
            return
        await self.service.reset_guild(
            guild_id=ctx.guild.id,
            admin_id=ctx.author.id,
            reason=f"resetalllevels by {ctx.author}",
        )
        embed = discord.Embed(
            title="\U0001F504 All Levels Reset",
            description="All level data has been reset for this server",
            color=self.EMBED_COLOR,
        )
        await send(ctx, embed=embed)

    @commands.hybrid_command(
        name="clean-lb",
        description="Remove departed users from the leaderboard (Admin only)",
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def clean_lb(self, ctx: commands.Context):
        """Remove leveling data for users who are no longer in the server."""
        if ctx.guild is None:
            return
        await maybe_defer(ctx)

        active_ids = {m.id for m in ctx.guild.members}
        stats = await db.clean_departed_users(ctx.guild.id, active_ids)

        embed = discord.Embed(
            title="\u2705 Leaderboard cleaned successfully.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Users checked", value=str(stats["total_checked"]), inline=True)
        embed.add_field(name="Removed", value=str(stats["total_removed"]), inline=True)
        embed.add_field(name="Remaining", value=str(stats["total_remaining"]), inline=True)
        await send(ctx, embed=embed)

    # ──────────────────────────────────────────────────────────────────
    # Admin commands — Configuration
    # ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="setlevelchannel", description="Set the level-up announcement channel (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel for level-up announcements")
    async def setlevelchannel(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        if channel:
            await db.set_levelup_channel(ctx.guild.id, channel.id)
            embed = discord.Embed(
                title="\U0001F4E2 Level-Up Channel Set",
                description=f"Level-up announcements will be sent to {channel.mention}",
                color=self.EMBED_COLOR,
            )
        else:
            await db.set_levelup_channel(ctx.guild.id, None)
            embed = discord.Embed(
                title="\U0001F4E2 Level-Up Channel Removed",
                description="Level-up announcements will be sent in the same channel as messages",
                color=self.EMBED_COLOR,
            )
        await send(ctx, embed=embed)

    @commands.hybrid_command(name="addrole", description="Add a role reward for a level (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(level="The level", role="The role to award")
    async def addrole(self, ctx: commands.Context, level: int, role: discord.Role):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        if level < 1:
            await send(ctx, "\u274c Level must be 1 or higher!", ephemeral=True)
            return
        me = ctx.guild.me
        if me is None or role >= me.top_role:
            await send(ctx, "\u274c I cannot assign this role! It's higher than or equal to my highest role.", ephemeral=True)
            return
        if role.managed:
            await send(ctx, "\u274c This role is managed by an integration and cannot be assigned!", ephemeral=True)
            return
        await db.add_role_reward(ctx.guild.id, level, role.id)
        embed = discord.Embed(
            title="\U0001F3C6 Role Reward Added",
            description=f"Users will receive {role.mention} when they reach **Level {level}**",
            color=self.EMBED_COLOR,
        )
        await send(ctx, embed=embed)

    @commands.hybrid_command(name="removerole", description="Remove a role reward (Admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @app_commands.describe(level="The level to remove the role reward from")
    async def removerole(self, ctx: commands.Context, level: int):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        result = await db.remove_role_reward(ctx.guild.id, level)
        if result:
            embed = discord.Embed(
                title="\U0001F3C6 Role Reward Removed",
                description=f"Removed role reward for **Level {level}**",
                color=self.EMBED_COLOR,
            )
        else:
            embed = discord.Embed(
                title="Not Found",
                description=f"No role reward found for Level {level}",
                color=discord.Color.red(),
            )
        await send(ctx, embed=embed)

    @commands.hybrid_command(name="rolerewards", aliases=["listroles"], description="View all role rewards")
    @commands.guild_only()
    async def rolerewards(self, ctx: commands.Context):
        if ctx.guild is None:
            return
        await maybe_defer(ctx)
        role_rewards = await db.get_role_rewards(ctx.guild.id)
        if not role_rewards:
            await send(ctx, "No role rewards have been configured yet!", ephemeral=True)
            return
        embed = discord.Embed(
            title="\U0001F3C6 Role Rewards",
            description="Roles awarded for reaching specific levels",
            color=self.EMBED_COLOR,
        )
        rewards_text = ""
        for reward in role_rewards:
            role_id = reward["role_id"]
            role = ctx.guild.get_role(role_id)
            logger.info(
                "rolerewards: guild=%s level=%s role_id=%s resolved=%s",
                ctx.guild.id, reward["level"], role_id, role.id if role else None,
            )
            if role:
                rewards_text += f"**Level {reward['level']}** \u2192 {role.mention}\n"
            else:
                rewards_text += f"**Level {reward['level']}** \u2192 *Deleted Role*\n"
        embed.description = rewards_text
        await send(ctx, embed=embed)

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    async def _ensure_refresh_rewards(self, guild: discord.Guild, member: discord.Member) -> None:
        """Refresh role rewards for a member after admin XP changes."""
        try:
            await self.service.refresh_rewards(guild, member)
        except Exception:
            logger.exception("Failed to refresh rewards after admin action")


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
