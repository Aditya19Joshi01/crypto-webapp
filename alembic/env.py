from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.database import Base
from backend.models.price_model import Price

target_metadata = Base.metadata

# Override sqlalchemy.url from environment (DATABASE_URL)
database_url = os.getenv('DATABASE_URL')
if not database_url:
    # fallback to backend config if available (helps running alembic from container)
    try:
        from backend.config import DATABASE_URL as backend_db_url
        database_url = backend_db_url
    except Exception:
        raise RuntimeError('DATABASE_URL environment variable must be set for alembic')

# Alembic (and SQLAlchemy migrations) expect a synchronous DB URL. If the
# project uses an async driver (e.g. postgresql+asyncpg://...), strip the
# async driver suffix so alembic can connect using the sync driver.
if database_url.startswith("postgresql+") and "+async" in database_url:
    # replace driver suffix like +asyncpg or +aiopg -> remove 
    # e.g. postgresql+asyncpg://... -> postgresql://...
    import re
    database_url = re.sub(r"\+[^:]+", "", database_url, count=1)

config.set_main_option('sqlalchemy.url', database_url)

def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
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
