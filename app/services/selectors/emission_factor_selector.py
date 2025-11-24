"""
Selectors for EmissionFactor queries - async version.

Provides optimized query methods for retrieving emission factors.
Converted from Django ORM to SQLAlchemy async.

NOTE: This selector now delegates to EmissionFactorRepository for consistency.
Consider using EmissionFactorRepository directly in new code.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import EmissionFactorRepository
from app.database.schemas import EmissionFactorDBModel
from app.utils.constants import Scope


class EmissionFactorSelector:
    """
    Query optimization layer for EmissionFactor.

    All READ operations for emission factors should go through this selector.
    This class now delegates to EmissionFactorRepository for consistency.
    """

    def __init__(self, session: AsyncSession):
        """Initialize selector with database session."""
        self.session = session
        self.repo = EmissionFactorRepository(session)

    async def get_all(self) -> list[EmissionFactorDBModel]:
        """Get all emission factors."""
        return await self.repo.get_all()

    async def get_by_activity_type(self, activity_type: str) -> list[EmissionFactorDBModel]:
        """
        Get all emission factors for a specific activity type.

        Args:
            activity_type: Activity type (from ActivityType enum)

        Returns:
            List of EmissionFactorDBModel
        """
        return await self.repo.get_by_activity_type(activity_type)

    async def get_by_scope(self, scope: int) -> list[EmissionFactorDBModel]:
        """
        Get all emission factors for a specific GHG scope.

        Args:
            scope: GHG Protocol scope (1, 2, or 3)

        Returns:
            List of EmissionFactorDBModel
        """
        return await self.repo.get_by_scope(scope)

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
        # Get all Scope 3 factors first
        scope_3_factors = await self.get_scope_3_factors()
        # Filter by category
        return [f for f in scope_3_factors if f.category == category]

    async def search_by_identifier(self, search_term: str) -> list[EmissionFactorDBModel]:
        """
        Search emission factors by lookup identifier.

        Args:
            search_term: Search string

        Returns:
            List of matching EmissionFactorDBModel
        """
        return await self.repo.search_by_identifier(search_term)
