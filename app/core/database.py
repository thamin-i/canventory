"""Database configuration and session management."""

import logging
import typing as t

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import SETTINGS

LOGGER: logging.Logger = logging.getLogger(__name__)


class Base(DeclarativeBase):  # pylint: disable=too-few-public-methods
    """Base class for all database models."""


# Create async engine
ENGINE: AsyncEngine = create_async_engine(
    SETTINGS.database_url,
    echo=SETTINGS.debug,
    future=True,
)

# Create async session factory
ASYNC_SESSION_MAKER: async_sessionmaker[AsyncSession] = async_sessionmaker(
    ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> t.AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session.

    Yields:
        AsyncSession: An asynchronous database session.
    """
    async with ASYNC_SESSION_MAKER() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connection."""
    await ENGINE.dispose()
