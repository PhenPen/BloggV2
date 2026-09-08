"""Database engine and session plumbing.

The URL comes from :data:`app.config.settings.db_url` (PostgreSQL + psycopg).
Models live in ``app.models``; Alembic owns schema creation, so nothing here
creates tables.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

database_engine = create_async_engine(
    settings.db_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=settings.database_pool_pre_ping,
    pool_timeout=settings.database_pool_timeout_seconds,
    pool_recycle=settings.database_pool_recycle_seconds,
)


class Base(DeclarativeBase):
    """Declarative base every ORM model inherits from."""


# expire_on_commit=False: after commit, keep loaded objects usable in memory.
# The async default would expire them and trigger implicit DB reloads on
# attribute access, which cannot be awaited and raises a MissingGreenlet error.
AsyncSessionLocal = async_sessionmaker(
    bind=database_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session():
    """Yield a database session; closes it when the request is done."""
    async with AsyncSessionLocal() as db_session:
        yield db_session