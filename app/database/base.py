"""
Database base configuration following kkb_fastapi pattern.

Handles PostgreSQL async engine creation and session management.
"""
import asyncio
import contextlib
import functools
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config as alembic_config
from sqlalchemy import Engine, text
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import Config

engine_kw = {
    "pool_pre_ping": True,
    # feature will normally emit SQL equivalent to "SELECT 1" each time a connection is checked out from the pool
    "pool_size": 2,  # number of connections to keep open at a time
    "max_overflow": 4,  # number of connections to allow to be opened above pool_size
    "connect_args": {
        "prepared_statement_cache_size": 0,  # disable prepared statement cache
        "statement_cache_size": 0,  # disable statement cache
    },
}


def get_db_url(config: Config) -> URL:
    """
    Construct database URL from config.
    """
    config_db = config.data["db"]
    return URL.create(drivername="postgresql+asyncpg", **config_db)


def get_async_engine(async_db_url: URL) -> Engine:
    """
    Create async database engine with connection pooling.
    """
    async_engine = create_async_engine(
        async_db_url,
        poolclass=QueuePool,
        pool_recycle=3600,
        pool_pre_ping=True,
        pool_size=60,
        max_overflow=80,
        pool_timeout=30,
    )
    return async_engine


def get_async_session_maker(async_db_url: URL) -> sessionmaker:
    """
    Create async session maker.
    """
    async_engine = get_async_engine(async_db_url)
    async_session_maker = sessionmaker(
        bind=async_engine, expire_on_commit=False, class_=AsyncSession
    )
    return async_session_maker


async def create_database(config: Config) -> bool:
    """
    Ensures the database specified in the config exists.
    Connects to a maintenance database (e.g., 'postgres') to issue the CREATE DATABASE command.

    Args:
        config: The application configuration.

    Returns:
        True if the database was newly created by this function.
        False if the database already existed.

    Raises:
        ValueError: If the database name is missing in the configuration.
        Exception: If any other unexpected error occurs during the database creation process.
    """

    logging.info("Creating database...")
    # Work on a copy of the original DB parameters to avoid modifying the input config
    original_db_params_copy = config.data["db"].copy()
    target_database_name = original_db_params_copy.pop("database", None)

    if not target_database_name:
        logging.error("Database name not found in configuration for creation.")
        raise ValueError("Database name missing in configuration for creation.")

    # Prepare connection parameters for the maintenance database
    # Handle 'user' vs 'username' for URL creation, ensuring 'username' is used by URL.create
    if "user" in original_db_params_copy and "username" not in original_db_params_copy:
        original_db_params_copy["username"] = original_db_params_copy.pop("user")

    # Connect to the default 'postgres' maintenance database
    maintenance_db_connect_params = {**original_db_params_copy, "database": "postgres"}

    maintenance_url = URL.create(
        drivername="postgresql+asyncpg", **maintenance_db_connect_params
    )
    maintenance_engine = None
    try:
        maintenance_engine = get_async_engine(maintenance_url)
        logging.info(
            f"Attempting to create database '{target_database_name}' in {original_db_params_copy['host']} if it does not exist."
        )
        async with maintenance_engine.connect() as connection:
            # For PostgreSQL, CREATE DATABASE cannot run inside a transaction block.
            # We get a version of the connection configured for AUTOCOMMIT.
            autocommit_connection = await connection.execution_options(
                isolation_level="AUTOCOMMIT"
            )
            await autocommit_connection.execute(
                text(f'CREATE DATABASE "{target_database_name}"')
            )
        logging.info(f"Database '{target_database_name}' created successfully.")
        return True  # Database was newly created
    except DBAPIError as e:
        # Check for PostgreSQL specific error code '42P04' (duplicate_database)
        with contextlib.suppress(AttributeError):
            if (
                hasattr(e, "orig")
                and e.orig is not None
                and hasattr(e.orig, "pgcode")
                and e.orig.pgcode == "42P04"
            ):
                logging.warning(
                    f"Database '{target_database_name}' already exists (detected by pgcode '42P04'). No action taken."
                )
                return False  # Database already existed

        # If it's a DBAPIError but not the specific one we're handling, re-raise it.
        logging.error(
            f"A DBAPIError occurred while trying to create database '{target_database_name}': {e}"
        )
        raise
    except Exception as e:
        logging.error(
            f"An unexpected error occurred while trying to create database '{target_database_name}': {e}"
        )
        raise
    finally:
        if maintenance_engine:
            await maintenance_engine.dispose()

    # This should never be reached due to the try/except structure above
    return False


async def apply_db_migration(config: Config):
    """
    Apply database migrations synchronously to ensure they complete before the application starts.

    This function blocks until all migrations are complete, ensuring that the database schema
    is in a consistent state before any workers start processing requests.

    Args:
        config: The application configuration containing database connection details.
    """

    # First, create the database if it doesn't exist
    await create_database(config)

    # Set up Alembic configuration
    alembic_cfg = alembic_config(str(Path.cwd() / "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location", str(Path.cwd() / "alembic_migrations")
    )

    # Convert the async URL to a synchronous one for Alembic
    async_url = get_db_url(config)
    # Replace asyncpg with psycopg2 for synchronous operations
    sync_url = str(async_url).replace("postgresql+asyncpg", "postgresql")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

    # Run Alembic migrations synchronously in a thread pool to avoid blocking the event loop
    # This effectively makes the migration process synchronous from the application's perspective
    logging.info("Starting database migrations...")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, functools.partial(command.upgrade, alembic_cfg, "head")
    )
    logging.info("Database migration completed successfully")
