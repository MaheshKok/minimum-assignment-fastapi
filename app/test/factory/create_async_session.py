"""
Create async session for test factories following kkb_fastapi pattern.
"""
from contextlib import asynccontextmanager

from app.database.session_manager.db_session import Database


@asynccontextmanager
async def async_session():
    """
    Get async session from Database singleton.

    This ensures factories use the same database connection
    as the test app, making data visible across sessions.
    """
    async with Database() as session:
        yield session
