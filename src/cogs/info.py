"""Info Cog - Server/user information commands (non-moderation).

All commands are hybrid (prefix + slash).
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("miku.info")

EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord blurple


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        logger.info("Info cog loaded")

    async def _send(self, ctx: commands.Context, *args, **kwargs):
        if getattr(ctx, "interaction", None) is None:
            kwargs.pop("ephemeral", None)
        return await ctx.send(*args, **kwargs)

    @commands.hybrid_command(name="membercount", description="Show the server member count")
    async def membercount(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Member Count",
                    description="This command can only be used in a server.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        count = ctx.guild.member_count
        embed = discord.Embed(title="Member Count", description=str(count or "Unknown"), color=EMBED_COLOR)
        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="roleinfo", description="Show information about a role")
    @app_commands.describe(role="Role to inspect")
    async def roleinfo(self, ctx: commands.Context, role: discord.Role) -> None:
        if ctx.guild is None:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Role Info",
                    description="This command can only be used in a server.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=f"Role Info - {role.name}", color=EMBED_COLOR)
        embed.add_field(name="ID", value=str(role.id), inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoist", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        embed.add_field(name="Members", value=str(len(role.members)), inline=True)
        embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:F>", inline=False)

        perms = [name.replace("_", " ").title() for name, v in role.permissions if v]
        perms_display = ", ".join(perms[:25]) if perms else "None"
        if len(perms) > 25:
            perms_display = f"{perms_display} (+{len(perms) - 25} more)"
        embed.add_field(name="Permissions", value=perms_display[:1024], inline=False)

        await self._send(ctx, embed=embed)

    @commands.hybrid_command(name="channelinfo", description="Show information about a channel")
    @app_commands.describe(channel="Channel to inspect (defaults to current)")
    async def channelinfo(self, ctx: commands.Context, channel: Optional[discord.abc.GuildChannel] = None) -> None:
        if ctx.guild is None:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Channel Info",
                    description="This command can only be used in a server.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        ch = channel or getattr(ctx, "channel", None)
        if ch is None or not isinstance(ch, discord.abc.GuildChannel):
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Channel Info",
                    description="Could not resolve that channel.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=f"Channel Info - {getattr(ch, 'name', 'Unknown')}", color=EMBED_COLOR)
        embed.add_field(name="ID", value=str(ch.id), inline=True)
        embed.add_field(name="Type", value=ch.type.name if hasattr(ch, "type") else type(ch).__name__, inline=True)
        category = getattr(ch, "category", None)
        category_name = category.name if category is not None else "None"
        embed.add_field(name="Category", value=category_name, inline=True)
        embed.add_field(name="Created", value=f"<t:{int(ch.created_at.timestamp())}:F>", inline=False)

        if isinstance(ch, discord.TextChannel):
            embed.add_field(name="NSFW", value="Yes" if ch.is_nsfw() else "No", inline=True)
            embed.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s", inline=True)
            embed.add_field(name="Topic", value=(ch.topic or "None")[:1024], inline=False)
        elif isinstance(ch, discord.VoiceChannel):
            embed.add_field(name="Bitrate", value=str(ch.bitrate), inline=True)
            embed.add_field(name="User Limit", value=str(ch.user_limit or 0), inline=True)

        await self._send(ctx, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))
