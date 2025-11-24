"""
Repository for EmissionResult database operations.

Handles all database interactions for emission calculation results.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.base import BaseRepository
from app.database.schemas import EmissionResultDBModel


class EmissionResultRepository(BaseRepository[EmissionResultDBModel]):
    """Repository for emission result operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize emission result repository.

        Args:
            session: Async database session
        """
        super().__init__(EmissionResultDBModel, session)

    async def get_by_activity_id(
        self, activity_id: UUID
    ) -> Optional[EmissionResultDBModel]:
        """
        Get emission result for a specific activity.

        Args:
            activity_id: Activity UUID

        Returns:
            Most recent emission result for the activity, or None
        """
        stmt = (
            select(self.model)
            .where(self.model.activity_id == activity_id)
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_by_activity_id(
        self, activity_id: UUID
    ) -> List[EmissionResultDBModel]:
        """
        Get all emission results for a specific activity (including historical).

        Args:
            activity_id: Activity UUID

        Returns:
            List of emission results ordered by created_at descending
        """
        stmt = (
            select(self.model)
            .where(self.model.activity_id == activity_id)
            .order_by(self.model.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_activity_ids(
        self, activity_ids: List[UUID]
    ) -> List[EmissionResultDBModel]:
        """
        Get emission results for multiple activities.

        Returns the most recent result for each activity.

        Args:
            activity_ids: List of activity UUIDs

        Returns:
            List of emission results
        """
        stmt = select(self.model).where(self.model.activity_id.in_(activity_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_results(
        self, skip: int = 0, limit: int = 100
    ) -> List[EmissionResultDBModel]:
        """
        Get all emission results with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of emission results
        """
        stmt = (
            select(self.model)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_activity_id(self, activity_id: UUID) -> int:
        """
        Delete all emission results for a specific activity.

        Useful when recalculating emissions.

        Args:
            activity_id: Activity UUID

        Returns:
            Number of results deleted
        """
        from sqlalchemy import delete

        stmt = delete(self.model).where(self.model.activity_id == activity_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_results_by_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[EmissionResultDBModel]:
        """
        Get emission results created within a date range.

        Args:
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of emission results
        """
        stmt = (
            select(self.model)
            .where(
                self.model.created_at >= start_date,
                self.model.created_at <= end_date,
            )
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_total_emissions(self) -> float:
        """
        Calculate total CO2e emissions across all results.

        Returns:
            Total CO2e in tonnes
        """
        stmt = select(func.sum(self.model.co2e_tonnes))
        result = await self.session.execute(stmt)
        total = result.scalar()
        return float(total) if total else 0.0

    async def get_emissions_by_scope(self) -> dict:
        """
        Get total emissions grouped by scope.

        Returns:
            Dict with scope totals: {'scope_2': float, 'scope_3': float}
        """
        # This requires joining with EmissionFactor to get scope information
        # For now, return empty dict (can be enhanced later)
        return {"scope_2": 0.0, "scope_3": 0.0}

    async def count_results_for_activity(self, activity_id: UUID) -> int:
        """
        Count number of emission results for a specific activity.

        Args:
            activity_id: Activity UUID

        Returns:
            Number of results
        """
        stmt = select(func.count()).where(self.model.activity_id == activity_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_latest_results(self, limit: int = 10) -> List[EmissionResultDBModel]:
        """
        Get the most recently calculated emission results.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of emission results ordered by created_at descending
        """
        stmt = select(self.model).order_by(self.model.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_result(
        self, result_id: UUID, **data
    ) -> Optional[EmissionResultDBModel]:
        """
        Update an emission result.

        Args:
            result_id: Result UUID
            **data: Fields to update

        Returns:
            Updated result if found, None otherwise
        """
        return await self.update(result_id, **data)

    async def get_results_with_low_confidence(
        self, threshold: float = 0.8, skip: int = 0, limit: int = 100
    ) -> List[EmissionResultDBModel]:
        """
        Get emission results with confidence score below threshold.

        Useful for identifying calculations that may need review.

        Args:
            threshold: Confidence score threshold
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of low-confidence emission results
        """
        stmt = (
            select(self.model)
            .where(self.model.confidence_score < threshold)
            .order_by(self.model.confidence_score.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
