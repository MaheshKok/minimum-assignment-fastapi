"""
Repository for Activity database operations.

Handles all database interactions for all activity types (Electricity, Air Travel, Goods & Services).
"""
from datetime import date
from typing import Dict, List, Optional, Type, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.base import BaseRepository
from app.database.schemas import (
    AirTravelActivityDBModel,
    ElectricityActivityDBModel,
    GoodsServicesActivityDBModel,
)

ActivityModelType = Union[
    ElectricityActivityDBModel,
    AirTravelActivityDBModel,
    GoodsServicesActivityDBModel,
]


class ActivityRepository(BaseRepository[ActivityModelType]):
    """
    Repository for activity operations across all activity types.

    Supports electricity, air travel, and goods & services activities.
    """

    # Model type mapping
    MODEL_MAP: Dict[str, Type[ActivityModelType]] = {
        "electricity": ElectricityActivityDBModel,
        "air_travel": AirTravelActivityDBModel,
        "goods_services": GoodsServicesActivityDBModel,
    }

    def __init__(
        self,
        session: AsyncSession,
        activity_type: str = "electricity",
    ):
        """
        Initialize activity repository.

        Args:
            session: Async database session
            activity_type: Type of activity ('electricity', 'air_travel', 'goods_services')

        Raises:
            ValueError: If activity_type is not recognized
        """
        if activity_type not in self.MODEL_MAP:
            raise ValueError(
                f"Invalid activity_type: {activity_type}. "
                f"Must be one of: {list(self.MODEL_MAP.keys())}"
            )

        model = self.MODEL_MAP[activity_type]
        super().__init__(model, session)
        self.activity_type = activity_type

    async def get_all_active(
        self, skip: int = 0, limit: int = 100
    ) -> List[ActivityModelType]:
        """
        Get all active (non-deleted) activities.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active activities
        """
        stmt = (
            select(self.model)
            .where(self.model.is_deleted == False)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_active(self, id: UUID) -> Optional[ActivityModelType]:
        """
        Get active (non-deleted) activity by ID.

        Args:
            id: Activity UUID

        Returns:
            Activity if found and not deleted, None otherwise
        """
        stmt = select(self.model).where(
            self.model.id == id, self.model.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_date_range(
        self, start_date: date, end_date: date, skip: int = 0, limit: int = 100
    ) -> List[ActivityModelType]:
        """
        Get activities within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of activities within the date range
        """
        stmt = (
            select(self.model)
            .where(
                self.model.date >= start_date,
                self.model.date <= end_date,
                self.model.is_deleted == False,
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_calculation(
        self, skip: int = 0, limit: int = 100
    ) -> List[ActivityModelType]:
        """
        Get activities that don't have emission calculations yet.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of activities without emission results
        """
        # This requires a join with EmissionResult to find activities without results
        # For now, return all active activities (filtering can be done in service layer)
        return await self.get_all_active(skip=skip, limit=limit)

    async def soft_delete(self, id: UUID) -> Optional[ActivityModelType]:
        """
        Soft delete activity by ID.

        Args:
            id: Activity UUID

        Returns:
            Updated activity if found, None otherwise
        """
        return await self.update(id, is_deleted=True)

    async def restore(self, id: UUID) -> Optional[ActivityModelType]:
        """
        Restore soft-deleted activity.

        Args:
            id: Activity UUID

        Returns:
            Updated activity if found, None otherwise
        """
        return await self.update(id, is_deleted=False)

    async def count_active(self) -> int:
        """
        Count active (non-deleted) activities.

        Returns:
            Number of active activities
        """
        return await self.count(filters={"is_deleted": False})


class ElectricityActivityRepository(ActivityRepository):
    """Repository specifically for electricity activities."""

    def __init__(self, session: AsyncSession):
        """Initialize electricity activity repository."""
        super().__init__(session, activity_type="electricity")

    async def get_by_country(
        self, country: str, skip: int = 0, limit: int = 100
    ) -> List[ElectricityActivityDBModel]:
        """
        Get electricity activities by country.

        Args:
            country: Country name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of activities for the specified country
        """
        stmt = (
            select(self.model)
            .where(
                self.model.country == country,
                self.model.is_deleted == False,
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AirTravelActivityRepository(ActivityRepository):
    """Repository specifically for air travel activities."""

    def __init__(self, session: AsyncSession):
        """Initialize air travel activity repository."""
        super().__init__(session, activity_type="air_travel")

    async def get_by_flight_range(
        self, flight_range: str, skip: int = 0, limit: int = 100
    ) -> List[AirTravelActivityDBModel]:
        """
        Get air travel activities by flight range.

        Args:
            flight_range: Flight range (e.g., 'Short-haul', 'Long-haul')
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of activities for the specified flight range
        """
        stmt = (
            select(self.model)
            .where(
                self.model.flight_range == flight_range,
                self.model.is_deleted == False,
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class GoodsServicesActivityRepository(ActivityRepository):
    """Repository specifically for goods & services activities."""

    def __init__(self, session: AsyncSession):
        """Initialize goods & services activity repository."""
        super().__init__(session, activity_type="goods_services")

    async def get_by_category(
        self, supplier_category: str, skip: int = 0, limit: int = 100
    ) -> List[GoodsServicesActivityDBModel]:
        """
        Get goods & services activities by supplier category.

        Args:
            supplier_category: Supplier category
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of activities for the specified category
        """
        stmt = (
            select(self.model)
            .where(
                self.model.supplier_category == supplier_category,
                self.model.is_deleted == False,
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
