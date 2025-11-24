"""
Database package following kkb_fastapi pattern.
"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()

__all__ = ["Base"]
