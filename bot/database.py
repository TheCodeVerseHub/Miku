from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .config import settings

DATABASE_URL = str(settings.database_url)

# Create async engine with asyncpg
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=0,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keeps attributes accessible after commit
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields an async database session.
    The session is properly rolled back and closed when an exception occurs.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db():
    """
    Close the async database engine.
    This function should be called when the bot is shutting down to properly clean up the database connection.
    """
    await engine.dispose()
