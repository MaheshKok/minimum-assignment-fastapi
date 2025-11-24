"""
Create async session for test factories following kkb_fastapi pattern.
"""
from app.database.session_manager.db_session import Database


class LazySessionMaker:
    """
    Lazy wrapper around Database's session maker.

    Acts like a sessionmaker but lazily gets it from Database singleton.
    This ensures factories use the same session maker as the test app.
    """

    def __call__(self):
        """
        Create and return a new async session.

        Returns an AsyncSession that can be used as an async context manager.
        """
        if Database._async_session_maker is None:
            raise RuntimeError(
                "Database not initialized. Call Database.init() in conftest first."
            )
        # Call the sessionmaker to get a new session
        return Database._async_session_maker()


# Create singleton instance that factories will use
async_session = LazySessionMaker()
