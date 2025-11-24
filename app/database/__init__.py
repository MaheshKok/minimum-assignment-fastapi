"""
Database package following kkb_fastapi pattern.
"""
from sqlalchemy.orm import declarative_base

from app.database.session_manager.db_session import Database

Base = declarative_base()

__all__ = ["Base", "Database"]
