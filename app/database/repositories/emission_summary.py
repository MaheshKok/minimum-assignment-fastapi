"""
EmissionSummary Repository.

Repository for querying pre-aggregated emission summaries.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.base import BaseRepository
from app.database.schemas.emission_summary import EmissionSummaryDBModel


class EmissionSummaryRepository(BaseRepository[EmissionSummaryDBModel]):
    """Repository for emission summary operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(EmissionSummaryDBModel, session)

    async def get_by_date_range(
        self,
        from_date: date,
        to_date: date,
        scope: Optional[int] = None,
        category: Optional[int] = None,
        activity_type: Optional[str] = None,
    ) -> list[EmissionSummaryDBModel]:
        """
        Get summaries for a date range with optional filters.

        Args:
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            scope: Optional scope filter (2 or 3)
            category: Optional category filter (1 or 6)
            activity_type: Optional activity type filter

        Returns:
            List of emission summaries matching the criteria
        """
        stmt = select(EmissionSummaryDBModel).where(
            and_(
                EmissionSummaryDBModel.from_date >= from_date,
                EmissionSummaryDBModel.to_date <= to_date,
            )
        )

        # Apply filters
        if scope is not None:
            stmt = stmt.where(EmissionSummaryDBModel.scope == scope)
        if category is not None:
            stmt = stmt.where(EmissionSummaryDBModel.category == category)
        if activity_type is not None:
            stmt = stmt.where(EmissionSummaryDBModel.activity_type == activity_type)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_summary(
        self,
        scope: Optional[int] = None,
        category: Optional[int] = None,
        activity_type: Optional[str] = None,
    ) -> Optional[EmissionSummaryDBModel]:
        """
        Get the most recent summary matching the filter criteria.

        Args:
            scope: Optional scope filter
            category: Optional category filter
            activity_type: Optional activity type filter

        Returns:
            Latest emission summary or None
        """
        stmt = select(EmissionSummaryDBModel).order_by(
            EmissionSummaryDBModel.to_date.desc()
        )

        # Apply filters
        if scope is not None:
            stmt = stmt.where(EmissionSummaryDBModel.scope == scope)
        if category is not None:
            stmt = stmt.where(EmissionSummaryDBModel.category == category)
        if activity_type is not None:
            stmt = stmt.where(EmissionSummaryDBModel.activity_type == activity_type)

        stmt = stmt.limit(1)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_monthly_summaries(
        self,
        year: int,
        month: int,
        scope: Optional[int] = None,
        category: Optional[int] = None,
        activity_type: Optional[str] = None,
    ) -> list[EmissionSummaryDBModel]:
        """
        Get all summaries for a specific month.

        Args:
            year: Year
            month: Month (1-12)
            scope: Optional scope filter
            category: Optional category filter
            activity_type: Optional activity type filter

        Returns:
            List of emission summaries for the month
        """
        # Calculate month boundaries
        from_date = date(year, month, 1)
        if month == 12:
            to_date = date(year, 12, 31)
        else:
            to_date = date(year, month + 1, 1)

        return await self.get_by_date_range(
            from_date=from_date,
            to_date=to_date,
            scope=scope,
            category=category,
            activity_type=activity_type,
        )

    async def get_summary_by_filters(
        self,
        from_date: date,
        to_date: date,
        scope: Optional[int] = None,
        category: Optional[int] = None,
        activity_type: Optional[str] = None,
        summary_type: Optional[str] = None,
    ) -> Optional[EmissionSummaryDBModel]:
        """
        Get a specific summary matching exact filter criteria.

        Useful for finding pre-calculated summaries for specific queries.

        Args:
            from_date: Exact start date
            to_date: Exact end date
            scope: Exact scope value (or None)
            category: Exact category value (or None)
            activity_type: Exact activity type (or None)
            summary_type: Type of summary (daily, monthly, etc.)

        Returns:
            Matching summary or None
        """
        stmt = select(EmissionSummaryDBModel).where(
            and_(
                EmissionSummaryDBModel.from_date == from_date,
                EmissionSummaryDBModel.to_date == to_date,
                EmissionSummaryDBModel.scope == scope,
                EmissionSummaryDBModel.category == category,
                EmissionSummaryDBModel.activity_type == activity_type,
            )
        )

        if summary_type is not None:
            stmt = stmt.where(EmissionSummaryDBModel.summary_type == summary_type)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
