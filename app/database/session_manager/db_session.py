"""
Database session manager following kkb_fastapi pattern.

Provides async context manager for database sessions.
"""
import logging

from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


class Database:
    """
    Database session manager with context manager support.

    Usage:
        Database.init(db_url, engine_kw=engine_kw)

        async with Database() as session:
            # use session
            result = await session.execute(select(Model))
    """

    _async_session_maker: sessionmaker | None = None

    @classmethod
    def init(cls, async_db_url: URL, engine_kw: dict = None):
        """
        Initialize the database session maker.

        Args:
            async_db_url: Database URL
            engine_kw: Engine keyword arguments
        """
        if engine_kw is None:
            engine_kw = {}

        async_engine = create_async_engine(
            async_db_url,
            **engine_kw,
        )
        cls._async_session_maker = sessionmaker(
            bind=async_engine, expire_on_commit=False, class_=AsyncSession
        )
        logging.info("Database session maker initialized")

    def __init__(self):
        if self._async_session_maker is None:
            raise RuntimeError(
                "Database not initialized. Call Database.init() first."
            )
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        """
        Enter async context manager.
        """
        self.session = self._async_session_maker()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit async context manager.
        """
        if exc_type is not None:
            # Exception occurred, rollback
            await self.session.rollback()
            logging.error(f"Database transaction rolled back due to: {exc_val}")
        else:
            # No exception, commit
            await self.session.commit()

        await self.session.close()
        self.session = None
