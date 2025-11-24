"""
Database exceptions.
"""


class DatabaseNotInitialized(Exception):
    """Raised when database is not initialized."""


class DatabaseTransactionError(Exception):
    """Raised when database transaction fails."""
