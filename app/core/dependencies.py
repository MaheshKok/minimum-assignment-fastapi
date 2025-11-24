"""
FastAPI dependency injection functions following kkb_fastapi pattern.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session_manager.db_session import Database


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for database session.

    Usage in route:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_db_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()
    """
    async with Database() as session:
        yield session
