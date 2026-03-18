from typing import Any

from discord.ext import commands

from bot.config import settings


class UserNotDeveloper(commands.CheckFailure):
    def __init__(self, message: str, *args: Any) -> None:
        super().__init__(
            message,
            *args,
        )


def developer_only():
    async def predicate(ctx: commands.Context):
        if ctx.author.id not in settings.developer_ids:
            raise UserNotDeveloper("You must be a developer to use this command!")
        return True

    return commands.check(predicate)
