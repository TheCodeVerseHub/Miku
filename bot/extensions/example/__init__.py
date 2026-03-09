"""
This file is an example of how you can create a discord.py extension in this codebase.

You can practically put all of this into a single file - There is no need to make an entire directory.
I just wanted to show that it is possible to make a module in which you can use relative importing for the sake of better code organization.

When making a discord.py extension, the only important thing is that it must have an asynchronous setup function:

```python
# You can use MikuBot here in place of commands.Bot, if you want to bother importing it
async def setup(bot: commands.Bot) -> None:
    pass
```

This file also demonstrates how you can use a database within your extension.
Notice that we define a separate SQLAlchemy declarative base.
That is because every extension should have it's own independent database schema.
If extensions need each other's data, it should be done through explicit APIs (**not** the HTTP kind).

This file also demonstrates how you can separate your database logic into repositories and services,
though it is entirely optional. You can raw dog all your SQL straight in the Cog or anywhere else you want.
Despite that, for clarity's sake, I implore you to follow this structure. Even better if you use multiple files for it.

Example layout you might want to use:
```
.
├── cogs.py
├── __init__.py
├── models.py
├── repositories.py
├── services.py
└── ui.py
```
Again, remember that this is over exaggerated. You most likely won't need a separate file for each stereotype.

If you REALLY want to go overboard with this, you can use alembic for managing your migrations, but the exact setup will be
quite convoluted.
"""

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bot.database import get_session


class Base(DeclarativeBase):
    pass


class ExampleModel(Base):
    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    some_string: Mapped[str | None] = mapped_column(String, nullable=True)


class ExampleRepository:
    session: AsyncSession

    def __init__(self, session):
        self.session = session

    async def get_by_id(self, id: int) -> ExampleModel | None:
        return await self.session.get(ExampleModel, id)

    async def save(self, example: ExampleModel) -> ExampleModel:
        self.session.add(example)
        await self.session.flush()
        await self.session.refresh(example)
        return example

    async def delete(self, example: ExampleModel) -> None:
        await self.session.delete(example)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return


class ExampleService:
    repository: ExampleRepository

    def __init__(self, repository: ExampleRepository):
        self.repository = repository

    async def get_by_id(self, id: int) -> ExampleModel | None:
        return await self.repository.get_by_id(id)

    async def save(self, example: ExampleModel) -> ExampleModel:
        return await self.repository.save(example)

    async def delete(self, example: ExampleModel) -> None:
        await self.repository.delete(example)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return


class ExampleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        # We push our models to the database here.
        # You can really do it anywhere, I just wanted to show you how to do it.
        from bot.database import engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @commands.hybrid_command(
        name="ping", usage="ping", description="Responds with pong"
    )
    @commands.guild_only()
    @commands.has_permissions(send_messages=True)
    @commands.cooldown(1, 2, commands.BucketType.member)
    async def _ping(self, ctx: commands.Context):
        await ctx.reply("Pong!", ephemeral=True)

    @commands.hybrid_command(
        name="demo",
        usage="demo",
        description="This command doesn't do anything. It merely demonstrates the usage of a Service.",
    )
    @commands.guild_only()
    @commands.has_permissions(send_messages=True)
    @commands.cooldown(1, 2, commands.BucketType.member)
    async def _database_demo(self, ctx: commands.Context):
        # Database interactions can be slow. Defer in advance.
        await ctx.defer(ephemeral=True)
        # Retrieve a session to work with the DB
        async with get_session() as session:
            # Instantiate a service with said session
            async with ExampleService(ExampleRepository(session)) as example_service:
                # Do work with service
                example = ExampleModel(some_string="Hello world!")
                example = await example_service.save(example)
                generated_id = example.id
            # Commit changes done with the session (or do rollback if you don't want them to be saved)
            await session.commit()

        # And then you can send your response... or don't, ghost the user. I don't care. I'm just a comment in the code.
        await ctx.send(
            f"Generated ID: {generated_id}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExampleCog(bot))
