from io import BytesIO
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import discord
from discord.ext import commands

from bot.database import get_session

from .models.domain import MessageResult
from .models.sql import Base
from .repositories import LevelingProfileRepository
from .services.leveling import (
    LevelingProfileService,
    MessageEvaluationService,
    MessageService,
)
from .services.rank_card import RankCardGenerator


WORKER_COUNT = 4
QUEUE_SIZE = 10000

"""
Hello, poor unfortunate soul who had potentially been tasked with refactoring or updating this feature.
Let me address the elephant in the room: There is a background worker in the Cog.
The reason? If we ever get into a situation where the bot needs to process thousands of messages per second,
it will literally die on the spot and wither away.

The proposed solution? A queue.
By enforcing a set limit on how many messages can be processed at a time, we can for the most part avoid unbounded concurrency
and ensure that the bot can still handle other tasks while it's crying over the sheer amount of messages.

Now, I can't stress this enough, but we HAVE to log whenever the queue runs out of capacity, otherwise, the next person to
visit this file for the purpose of debugging will have a very, VERY long weekend.
"""


class LevelingCog(commands.Cog):
    _logger: logging.Logger

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._logger = logging.getLogger(self.__class__.__name__)

        self.message_evaluation_service = MessageEvaluationService()
        self.rank_card_generator = RankCardGenerator()

        self._queue: asyncio.Queue[discord.Message] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._workers: list[asyncio.Task] = []

    async def cog_load(self) -> None:
        from bot.database import engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Start workers
        for _ in range(WORKER_COUNT):
            task = asyncio.create_task(self._worker())
            self._workers.append(task)

    async def cog_unload(self) -> None:
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        await self.rank_card_generator.close()

    @asynccontextmanager
    async def get_profile_service(self) -> AsyncGenerator[LevelingProfileService]:
        """
        Returns a context manager that yields a LevelingProfileService instance.
        ! The instance is bound to a database session that is **committed** when the context manager is exited.
        """
        async with get_session() as session:
            try:
                yield LevelingProfileService(LevelingProfileRepository(session))
                await session.commit()
            except:
                raise

    @asynccontextmanager
    async def get_message_service(self) -> AsyncGenerator[MessageService]:
        """
        Returns a context manager that yields a MessageService instance.
        ! The instance is bound to a database session that is **committed** when the context manager is exited.
        The MessageService instance is created with the LevelingProfileService instance yielded by get_profile_service and the MessageEvaluationService instance.
        """
        async with self.get_profile_service() as profile_service:
            yield MessageService(profile_service, self.message_evaluation_service)

    async def _worker(self):
        """Background worker that processes queued messages."""
        while True:
            message = await self._queue.get()
            if not isinstance(message.author, discord.Member):
                self._logger.warning(
                    "Received message from non-member %s, this should not be possible.",
                    message.author,
                )
                continue

            try:
                async with self.get_message_service() as service:
                    result = await service.handle_message(message)

                if result.leveled_up:
                    await self._send_level_up(message.author, result)

            except Exception:
                self._logger.exception("Failed processing message %d", message.id)

            finally:
                self._queue.task_done()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Fast event handler that just enqueues messages."""

        if message.author.bot or not message.guild:
            return

        if not isinstance(message.author, discord.Member):
            return

        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            # If we ever decide to add live monitoring with Prometheus, this is where we'll implement queue capacity metrics
            self._logger.warning("Leveling queue full, dropping message %d", message.id)

    @commands.hybrid_command(
        name="level",
        usage="level",
        description="Responds with your level",
    )
    @commands.guild_only()
    @commands.has_permissions(send_messages=True)
    @commands.cooldown(1, 2, commands.BucketType.member)
    async def _level(self, ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member):
            return
        async with self.get_profile_service() as service:
            profile = await service.get_or_create_profile(ctx.author)
            rank_card = await self.rank_card_generator.generate_rank_card(
                # Avatar
                (
                    ctx.author.avatar.url
                    if ctx.author.avatar
                    else ctx.author.default_avatar.url
                ),
                # Username
                ctx.author.display_name,
                # Rank
                1,
                # Level
                profile.level,
                # Current ExP
                round(
                    profile.experience
                    - MessageEvaluationService.calculate_experience_for_level(
                        profile.level
                    )
                ),
                # Next ExP
                round(
                    MessageEvaluationService.calculate_experience_for_level(
                        profile.level + 1
                    )
                ),
                # Total ExP
                round(profile.experience),
                # Total messages
                0,
            )
            await ctx.reply(
                file=discord.File(BytesIO(rank_card), "rank_card.png"), ephemeral=True
            )

    async def _send_level_up(self, member: discord.Member, result: MessageResult):
        # TODO: Implement
        self._logger.warning(
            "Level up not implemented yet! (%d is now level %d)",
            member.id,
            result.current_level,
        )
