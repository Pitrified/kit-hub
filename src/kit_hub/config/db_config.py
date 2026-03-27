"""Database configuration model.

Defines the shape of the database connection settings.  No environment
variables are read here - that belongs in ``DbParams``.

See Also:
    ``DbParams`` - the companion class that loads actual values.
    ``docs/guides/params_config.md`` - Config / Params pattern reference.
"""

from kit_hub.data_models.basemodel_kwargs import BaseModelKwargs


class DbConfig(BaseModelKwargs):
    """Database connection configuration.

    Attributes:
        db_url: SQLAlchemy database URL.  For SQLite with async support
            use ``sqlite+aiosqlite:///path/to/db.sqlite``.
        echo: When ``True``, SQLAlchemy logs all emitted SQL statements.
            Useful for debugging; keep ``False`` in production.
    """

    db_url: str
    echo: bool = False
