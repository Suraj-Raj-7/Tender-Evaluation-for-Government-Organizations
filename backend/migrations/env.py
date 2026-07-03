"""
backend/migrations/env.py
----------------------------
Purpose: Alembic's control script. Tells Alembic two things it needs to
compare and apply migrations: (1) what the database SHOULD look like
(from our SQLAlchemy models), and (2) how to actually connect to the
real PostgreSQL database.

Why this file exists: Without this, Alembic would have no idea our
project even has models, or how to reach our database -- it would just
be an empty migration tool with nothing to compare against.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import our actual database setup and every model, so Alembic knows
# exactly what tables should exist. Importing app.models triggers
# models/__init__.py, which imports all 12 model files.
from app.database import Base
from app.config import settings
import app.models  # noqa: F401 -- imported for its side effect of registering all tables

# Alembic's config object, giving access to values in alembic.ini.
config = context.config

# Overrides whatever (blank) sqlalchemy.url is in alembic.ini with the
# real one from our .env file, read through settings.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Sets up Python logging as configured in alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic compares against the real database to detect
# differences (missing tables, changed columns, etc.) when autogenerating.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Purpose: Generates SQL scripts without needing a live database
    connection (used for generating .sql files to run manually elsewhere).
    We don't use this mode in this project, but Alembic requires it to
    be defined.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Purpose: Runs migrations with a real, live connection to PostgreSQL.
    This is the mode we actually use every time we run
    'alembic upgrade head' or 'alembic revision --autogenerate'.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()