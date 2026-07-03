"""Global command cooldown system.

Applies a per-user, per-command cooldown to every command in the bot via a
global check (bot.add_check), so individual commands don't need to opt in
with their own @commands.cooldown decorator.
"""

from discord.ext import commands

from utils.cooldowns import cooldown_manager, CommandOnCooldown


class CommandHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_check(self.global_cooldown_check)

    async def global_cooldown_check(self, ctx: commands.Context) -> bool:
        if ctx.command is None:
            return True

        retry_after = cooldown_manager.check(ctx.author.id, ctx.command.qualified_name)
        if retry_after > 0:
            raise CommandOnCooldown(retry_after)
        return True


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandHandler(bot))