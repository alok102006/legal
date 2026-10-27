import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

_engine_kwargs: dict = {"echo": os.environ.get("SQL_ECHO", "").lower() in ("1", "true"), "future": True}
if settings.env == "test":
    # one connection per use: tests create many short-lived event loops
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=10)

# Create async database engine
engine = create_async_engine(settings.database_url, **_engine_kwargs)

# Async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
