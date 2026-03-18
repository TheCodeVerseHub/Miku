"""
MIKU Developer Commands
"""

import logging

import discord
from discord.ext import commands

from bot import MikuBot
from bot.config import settings

from .guards import developer_only


class DeveloperCog(commands.Cog):
    _logger: logging.Logger

    def __init__(self, bot: MikuBot):
        self.bot = bot
        self._logger = logging.getLogger(self.__class__.__name__)

    @commands.hybrid_group(
        name="extension",
        aliases=["ext"],
        description="Allows managing extensions during runtime.",
    )
    @developer_only()
    async def extensions(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("You must specify a subcommand.", ephemeral=True)

    def _emoji_for(self, extension: str) -> str:
        emojis = ""
        if extension in self.bot.missing_optional:
            emojis += " 🔴"
        elif extension in self.bot.extensions.keys():
            emojis += " 🟢"
        elif extension in self.bot.available_extensions:
            emojis += " 🟡"
        if extension in settings.core_extensions:
            emojis += " 🔒"
        elif extension in settings.additional_extensions:
            emojis += " ⚙️"
        return emojis.strip()

    @extensions.command(
        name="list",
        description="Lists all extensions.",
    )
    async def _extensions_list(self, ctx: commands.Context):
        avail = self.bot.available_extensions
        missing = self.bot.missing_optional

        body = ""

        for core_extension in sorted(missing | avail):
            body += f"- {self._emoji_for(core_extension)} {core_extension}\n"

        footer = """-# 🔴: Missing
-# 🟡: Available
-# 🟢: Loaded
-# ⚙️: Auto-load / Additional
-# 🔒: Required / Core"""

        await ctx.send("## Extensions" + "\n" + body.strip() + "\n" + footer)

    @extensions.command(
        name="refresh",
        description="Re-runs extension discovery process.",
    )
    async def _extensions_refresh(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        # This implementation is very scuffed since extension discovery isn't abstracted properly
        from bot import _find_available_extensions

        self.bot.available_extensions = _find_available_extensions()
        self.bot.missing_optional = (
            set(settings.additional_extensions) - self.bot.available_extensions
        )
        await ctx.send("Refreshed the extension list.", ephemeral=True)

    @extensions.command(
        name="reload",
        description="Reloads an extension.",
    )
    async def _extensions_reload(self, ctx: commands.Context, extension: str):
        await ctx.defer(ephemeral=True)
        try:
            await self.bot.reload_extension(extension)
            self._logger.info(
                "%d has reloaded the %s extension.", ctx.author.id, extension
            )
            await ctx.send(f"Reloaded {extension} extension.", ephemeral=True)
        except commands.ExtensionError as e:
            await ctx.send(
                f"Failed to reload {extension} extension: {e}", ephemeral=True
            )
            self._logger.error(
                "Failed to reload %s extension (requested by %d): %s",
                extension,
                ctx.author.id,
                e,
            )
            raise

    @extensions.command(
        name="unload",
        description="Unloads an extension.",
    )
    async def _extensions_unload(self, ctx: commands.Context, extension: str):
        await ctx.defer(ephemeral=True)
        try:
            await self.bot.unload_extension(extension)
            self._logger.info(
                "%d has unloaded the %s extension.", ctx.author.id, extension
            )
            await ctx.send(f"Unloaded {extension} extension.", ephemeral=True)
        except commands.ExtensionError as e:
            await ctx.send(
                f"Failed to unload {extension} extension: {e}", ephemeral=True
            )
            self._logger.error(
                "Failed to unload %s extension (requested by %d): %s",
                extension,
                ctx.author.id,
                e,
            )
            raise

    @extensions.command(
        name="load",
        description="Loads an extension.",
    )
    async def _extensions_load(self, ctx: commands.Context, extension: str):
        await ctx.defer(ephemeral=True)
        try:
            await self.bot.load_extension(extension)
            self._logger.info(
                "%d has loaded the %s extension.", ctx.author.id, extension
            )
            await ctx.send(f"Loaded {extension} extension.", ephemeral=True)
        except commands.ExtensionError as e:
            await ctx.send(f"Failed to load {extension} extension: {e}", ephemeral=True)
            self._logger.error(
                "Failed to load %s extension (requested by %d): %s",
                extension,
                ctx.author.id,
                e,
            )
            raise


async def setup(bot: MikuBot) -> None:
    await bot.add_cog(DeveloperCog(bot))
