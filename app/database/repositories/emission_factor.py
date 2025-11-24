"""
Repository for EmissionFactor database operations.

Handles all database interactions for emission factors.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.base import BaseRepository
from app.database.schemas import EmissionFactorDBModel


class EmissionFactorRepository(BaseRepository[EmissionFactorDBModel]):
    """Repository for emission factor operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize emission factor repository.

        Args:
            session: Async database session
        """
        super().__init__(EmissionFactorDBModel, session)

    async def get_by_activity_type(
        self, activity_type: str, skip: int = 0, limit: int = 100
    ) -> List[EmissionFactorDBModel]:
        """
        Get emission factors by activity type.

        Args:
            activity_type: Type of activity (e.g., 'Electricity', 'Air Travel')
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of emission factors matching the activity type
        """
        stmt = (
            select(self.model)
            .where(self.model.activity_type == activity_type)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_scope(
        self, scope: int, skip: int = 0, limit: int = 100
    ) -> List[EmissionFactorDBModel]:
        """
        Get emission factors by GHG scope.

        Args:
            scope: GHG Protocol scope (1, 2, or 3)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of emission factors in the specified scope
        """
        stmt = (
            select(self.model)
            .where(self.model.scope == scope)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_lookup_identifier(
        self, lookup_identifier: str
    ) -> Optional[EmissionFactorDBModel]:
        """
        Get emission factor by lookup identifier.

        Args:
            lookup_identifier: Unique lookup identifier

        Returns:
            Emission factor if found, None otherwise
        """
        stmt = select(self.model).where(
            self.model.lookup_identifier == lookup_identifier
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def search_by_identifier(
        self, identifier: str, activity_type: Optional[str] = None
    ) -> List[EmissionFactorDBModel]:
        """
        Search emission factors by partial identifier match.

        Args:
            identifier: Partial identifier to search for
            activity_type: Optional activity type filter

        Returns:
            List of matching emission factors
        """
        stmt = select(self.model).where(
            self.model.lookup_identifier.ilike(f"%{identifier}%")
        )

        if activity_type:
            stmt = stmt.where(self.model.activity_type == activity_type)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_activity_type_and_category(
        self, activity_type: str, category: Optional[int] = None
    ) -> List[EmissionFactorDBModel]:
        """
        Get emission factors by activity type and optional category.

        Args:
            activity_type: Type of activity
            category: Optional Scope 3 category (1-15)

        Returns:
            List of matching emission factors
        """
        stmt = select(self.model).where(self.model.activity_type == activity_type)

        if category is not None:
            stmt = stmt.where(self.model.category == category)
        else:
            stmt = stmt.where(self.model.category.is_(None))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_active(
        self, skip: int = 0, limit: int = 100
    ) -> List[EmissionFactorDBModel]:
        """
        Get all active (non-deleted) emission factors.

        Note: EmissionFactor doesn't have soft delete, so this returns all records.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of emission factors
        """
        return await self.get_all(skip=skip, limit=limit)
