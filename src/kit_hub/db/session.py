"""Async SQLAlchemy engine and session management.

``DatabaseSession`` wraps the SQLAlchemy async engine lifecycle:
creating tables on startup, providing a session factory during normal
operation, and disposing the engine on shutdown.

Usage example::

    config = DbConfig(db_url="sqlite+aiosqlite:///data/kit_hub.db")
    db = DatabaseSession(config)
    await db.init_db()

    async with db.get_session() as session:
        # perform async ORM operations
        ...

    await db.close()
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger as lg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import text

from kit_hub.config.db_config import DbConfig
from kit_hub.db.models import Base


class DatabaseSession:
    """Manages the async SQLAlchemy engine and session factory.

    One instance of this class is created per process (typically by
    ``KitHubParams`` or app lifespan code) and shared across all
    services that need database access.

    Attributes:
        config: Typed database connection configuration.
    """

    def __init__(self, config: DbConfig) -> None:
        """Initialise with the given config.

        The engine is created immediately but tables are not created until
        ``init_db()`` is called.

        Args:
            config: Database connection configuration.
        """
        self.config = config
        connect_args: dict = {"check_same_thread": False}
        # StaticPool is required for in-memory SQLite in async tests so that
        # all connections share the same database.
        is_memory = ":memory:" in config.db_url
        if is_memory:
            self._engine = create_async_engine(
                config.db_url,
                echo=config.echo,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        else:
            self._engine = create_async_engine(
                config.db_url,
                echo=config.echo,
                connect_args=connect_args,
            )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self) -> None:
        """Create all tables and enable WAL mode for SQLite.

        Safe to call multiple times - SQLAlchemy uses ``CREATE TABLE IF NOT
        EXISTS`` internally.
        """
        lg.info("Initialising database: {}", self.config.db_url)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # WAL mode improves read concurrency and crash safety for SQLite.
            if "sqlite" in self.config.db_url:
                await conn.execute(text("PRAGMA journal_mode=WAL"))
        lg.success("Database initialised")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        """Yield an ``AsyncSession`` as a context manager.

        The session is committed on clean exit and rolled back on error.

        Yields:
            AsyncSession: An active SQLAlchemy async session.

        Raises:
            Exception: Re-raises any exception after rolling back the session.
        """
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Dispose the engine, closing all pooled connections."""
        lg.info("Closing database engine")
        await self._engine.dispose()
