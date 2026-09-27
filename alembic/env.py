"""Alembic environment for the backend tables in the central PostgreSQL DB.

The database already contains tables owned by the .NET EF system. Autogenerate
must never drop or alter those, so :func:`include_object` filters out any
reflected table that is not part of this app's metadata.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable when alembic runs from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Single source of truth for the connection (env / .env file, never tracked).
config.set_main_option("sqlalchemy.url", load_settings().database_url)

target_metadata = Base.metadata

#: Tables owned by other systems in the same database (never touched).
_OUR_TABLES = set(Base.metadata.tables)


def include_object(object, name, type_, reflected, compare_to):
    """Autogenerate only this app's tables; legacy tables are invisible."""
    if type_ == "table" and reflected and name not in _OUR_TABLES:
        return False
    if type_ == "index" and reflected and object.table.name not in _OUR_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
