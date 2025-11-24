"""
Database exceptions.
"""


class DatabaseNotInitialized(Exception):
    """Raised when database is not initialized."""
    pass


class DatabaseTransactionError(Exception):
    """Raised when database transaction fails."""
    pass
