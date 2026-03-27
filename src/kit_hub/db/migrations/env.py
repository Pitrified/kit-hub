"""Alembic environment configuration for kit-hub.

Configured for async SQLAlchemy with ``aiosqlite``.  The database URL is
read from ``KitHubParams`` so migrations always target the correct file for
the active environment (``ENV_STAGE_TYPE`` / ``ENV_LOCATION_TYPE``).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from kit_hub.db.models import Base
from kit_hub.params.db_params import DbParams

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Return the database URL for the active environment."""
    # Allow the URL to be overridden via the ini file (useful for offline mode).
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    db_config = DbParams().to_config()
    return db_config.db_url


def run_migrations_offline() -> None:
    """Run migrations without a live database connection.

    The URL is emitted to the script output rather than executed.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations within an active connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations in online mode."""
    url = _get_url()
    connectable = create_async_engine(url, echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live database connection (async)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
