"""
Selectors for EmissionFactor queries - async version.

Provides optimized query methods for retrieving emission factors.
Converted from Django ORM to SQLAlchemy async.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import EmissionFactorDBModel
from app.utils.constants import Scope


class EmissionFactorSelector:
    """
    Query optimization layer for EmissionFactor.

    All READ operations for emission factors should go through this selector.
    """

    def __init__(self, session: AsyncSession):
        """Initialize selector with database session."""
        self.session = session

    async def get_all(self) -> list[EmissionFactorDBModel]:
        """Get all emission factors."""
        stmt = select(EmissionFactorDBModel)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_activity_type(self, activity_type: str) -> list[EmissionFactorDBModel]:
        """
        Get all emission factors for a specific activity type.

        Args:
            activity_type: Activity type (from ActivityType enum)

        Returns:
            List of EmissionFactorDBModel
        """
        stmt = select(EmissionFactorDBModel).where(
            EmissionFactorDBModel.activity_type == activity_type
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_scope(self, scope: int) -> list[EmissionFactorDBModel]:
        """
        Get all emission factors for a specific GHG scope.

        Args:
            scope: GHG Protocol scope (1, 2, or 3)

        Returns:
            List of EmissionFactorDBModel
        """
        stmt = select(EmissionFactorDBModel).where(EmissionFactorDBModel.scope == scope)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_scope_2_factors(self) -> list[EmissionFactorDBModel]:
        """Get all Scope 2 emission factors."""
        return await self.get_by_scope(Scope.SCOPE_2)

    async def get_scope_3_factors(self) -> list[EmissionFactorDBModel]:
        """Get all Scope 3 emission factors."""
        return await self.get_by_scope(Scope.SCOPE_3)

    async def get_by_category(self, category: int) -> list[EmissionFactorDBModel]:
        """
        Get emission factors by Scope 3 category.

        Args:
            category: Category number (e.g., 1, 6)

        Returns:
            List of EmissionFactorDBModel
        """
        stmt = select(EmissionFactorDBModel).where(
            EmissionFactorDBModel.scope == Scope.SCOPE_3,
            EmissionFactorDBModel.category == category,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_identifier(self, search_term: str) -> list[EmissionFactorDBModel]:
        """
        Search emission factors by lookup identifier.

        Args:
            search_term: Search string

        Returns:
            List of matching EmissionFactorDBModel
        """
        stmt = select(EmissionFactorDBModel).where(
            EmissionFactorDBModel.lookup_identifier.ilike(f"%{search_term}%")
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
