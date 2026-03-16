"""
A modular re-implementation of Aditya's Leveling system for CVH.
"""

from discord.ext import commands

from .cogs import LevelingCog


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LevelingCog(bot))
