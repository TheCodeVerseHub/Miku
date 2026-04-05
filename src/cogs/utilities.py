"""Utility Cog - General non-moderation commands.

Commands are implemented as *hybrid commands* so they work as both:
- Prefix commands (e.g. `&ping`)
- Slash commands (e.g. `/ping`)

This cog intentionally avoids moderation actions (ban/kick/mute/clear/etc.).
"""

from __future__ import annotations

import logging
import platform
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("miku.utilities")

EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord blurple


def _format_timedelta(seconds: float) -> str:
    seconds_i = max(0, int(seconds))
    days, rem = divmod(seconds_i, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


class Utilities(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        logger.info("Utilities cog loaded")

    # -- hybrid-command helpers (same pattern as other cogs) -----------------

    async def _send(self, ctx: commands.Context, *args, **kwargs):
        interaction = getattr(ctx, "interaction", None)

        if interaction is None:
            kwargs.pop("ephemeral", None)

        try:
            return await ctx.send(*args, **kwargs)
        except discord.NotFound as e:
            if (
                interaction is not None
                and getattr(e, "code", None) == 10062
                and getattr(ctx, "channel", None) is not None
            ):
                kwargs.pop("ephemeral", None)
                return await ctx.channel.send(*args, **kwargs)  # type: ignore[union-attr]
            raise
        except discord.InteractionResponded:
            if interaction is not None:
                return await interaction.followup.send(*args, **kwargs)
            raise

    async def _maybe_defer(self, ctx: commands.Context, *, ephemeral: bool = False) -> None:
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return
        if interaction.response.is_done():
            return
        try:
            await ctx.defer(ephemeral=ephemeral)
        except (discord.NotFound, discord.HTTPException):
            return

    # =====================================================================
    # Commands
    # =====================================================================

    @commands.hybrid_command(name="ping", description="Check if the bot is responsive")
    async def ping(self, ctx: commands.Context) -> None:
        """Show bot latency."""
        latency_ms = round(getattr(self.bot, "latency", 0.0) * 1000)
        embed = discord.Embed(
            title="Pong!",
            description=f"Latency: **{latency_ms}ms**",
            color=EMBED_COLOR,
        )
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="uptime", description="Show how long the bot has been online")
    async def uptime(self, ctx: commands.Context) -> None:
        """Show bot uptime."""
        started_at: Optional[datetime] = getattr(self.bot, "start_time", None)
        if started_at is None:
            embed = discord.Embed(
                title="Uptime",
                description="Uptime tracking is not available in this build.",
                color=discord.Color.orange(),
            )
            await self._send(ctx, embed=embed, ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        delta_s = (now - started_at).total_seconds()

        embed = discord.Embed(
            title="Uptime",
            description=_format_timedelta(delta_s),
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Started {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="about", description="Learn more about Miku")
    async def about(self, ctx: commands.Context) -> None:
        """Show bot stats and version info."""
        await self._maybe_defer(ctx, ephemeral=False)

        guild_count = len(getattr(self.bot, "guilds", []))
        command_count = len(list(getattr(self.bot, "walk_commands", lambda: [])()))

        started_at: Optional[datetime] = getattr(self.bot, "start_time", None)
        if started_at is not None:
            uptime = _format_timedelta((datetime.now(timezone.utc) - started_at).total_seconds())
        else:
            uptime = "N/A"

        owner_text = "Unknown"
        try:
            app = await self.bot.application_info()  # type: ignore[attr-defined]
            owner = getattr(app, "owner", None)
            if owner is not None:
                owner_text = f"{owner}"
        except Exception:
            pass

        embed = discord.Embed(
            title="About Miku",
            description="A leveling-focused Discord bot with useful utilities.",
            color=EMBED_COLOR,
        )
        embed.add_field(name="Servers", value=str(guild_count), inline=True)
        embed.add_field(name="Commands", value=str(command_count), inline=True)
        embed.add_field(name="Uptime", value=uptime, inline=True)

        embed.add_field(name="Owner", value=owner_text, inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py", value=getattr(discord, "__version__", "Unknown"), inline=True)

        if self.bot.user is not None:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="invite", description="Get the bot invite link")
    async def invite(self, ctx: commands.Context) -> None:
        """Send an OAuth2 invite link for the bot."""
        if self.bot.user is None:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Invite",
                    description="Bot user is not ready yet. Try again in a moment.",
                    color=discord.Color.orange(),
                ),
                ephemeral=True,
            )
            return

        url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=discord.Permissions.none(),
            scopes=("bot", "applications.commands"),
        )

        embed = discord.Embed(
            title="Invite Miku",
            description=f"Click here to invite me to your server:\n{url}",
            color=EMBED_COLOR,
        )
        await self._send(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="avatar", description="Show a user's avatar")
    @app_commands.describe(user="User to view (defaults to you)")
    async def avatar(self, ctx: commands.Context, user: Optional[discord.User] = None) -> None:
        """Display avatar for a user."""
        target = user or ctx.author
        embed = discord.Embed(
            title=f"Avatar - {target}",
            color=EMBED_COLOR,
        )
        embed.set_image(url=target.display_avatar.url)
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="userinfo", description="Show information about a user")
    @app_commands.describe(user="User to view (defaults to you)")
    async def userinfo(self, ctx: commands.Context, user: Optional[discord.Member] = None) -> None:
        """Display basic info about a member."""
        if ctx.guild is None:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="User Info",
                    description="This command can only be used in a server.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        member = user or ctx.author
        if not isinstance(member, discord.Member):
            # Shouldn't happen in guild context, but keep it safe.
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="User Info",
                    description="Could not resolve that member.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Exclude @everyone and keep the output short.
        roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
        roles_display = ", ".join(roles[-15:]) if roles else "None"
        if len(roles) > 15:
            roles_display = f"{roles_display} (+{len(roles) - 15} more)"

        embed = discord.Embed(
            title=f"User Info - {member}",
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)

        embed.add_field(
            name="Created",
            value=f"<t:{int(member.created_at.timestamp())}:F>",
            inline=True,
        )
        if member.joined_at is not None:
            embed.add_field(
                name="Joined",
                value=f"<t:{int(member.joined_at.timestamp())}:F>",
                inline=True,
            )

        embed.add_field(name="Roles", value=roles_display, inline=False)
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Show information about this server")
    async def serverinfo(self, ctx: commands.Context) -> None:
        """Display server information."""
        if ctx.guild is None:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Server Info",
                    description="This command can only be used in a server.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        guild = ctx.guild

        embed = discord.Embed(
            title=f"Server Info - {guild.name}",
            color=EMBED_COLOR,
        )

        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Owner", value=str(guild.owner) if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=True)

        embed.add_field(name="Members", value=str(guild.member_count or "Unknown"), inline=True)
        embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="Voice Channels", value=str(len(guild.voice_channels)), inline=True)

        await self._send(ctx, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utilities(bot))
