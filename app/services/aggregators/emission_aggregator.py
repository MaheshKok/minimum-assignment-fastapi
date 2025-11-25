"""
Emission Aggregation Service.

Calculates and stores pre-aggregated emission summaries for efficient querying.
Handles aggregation by date range, scope, category, and activity type.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import (
    EmissionFactorDBModel,
    EmissionResultDBModel,
    EmissionSummaryDBModel,
)

logger = logging.getLogger(__name__)


class EmissionAggregator:
    """
    Service for aggregating emission results into summary tables.

    Aggregates emissions by:
    - Date range (daily, weekly, monthly, yearly, custom)
    - Scope (2, 3, or all)
    - Category (1, 6, or all)
    - Activity type (Electricity, Air Travel, Goods & Services, or all)
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def aggregate_daily_summaries(
        self,
        target_date: date,
    ) -> list[EmissionSummaryDBModel]:
        """
        Aggregate emissions for a single day.

        Creates summaries for:
        - All scopes, all categories, all activities
        - Each scope individually
        - Each scope + category combination
        - Each activity type
        - Combinations of scope + activity, category + activity
        """
        logger.info(f"Aggregating daily emissions for {target_date}")

        summaries = []

        # 1. Overall summary (no filters)
        overall = await self._aggregate_period(
            from_date=target_date,
            to_date=target_date,
            summary_type="daily",
        )
        if overall:
            summaries.append(overall)

        # 2. Summary by scope
        for scope in [2, 3]:
            scope_summary = await self._aggregate_period(
                from_date=target_date,
                to_date=target_date,
                scope=scope,
                summary_type="daily",
            )
            if scope_summary:
                summaries.append(scope_summary)

        # 3. Summary by scope + category
        for scope, category in [(3, 1), (3, 6)]:
            scope_cat_summary = await self._aggregate_period(
                from_date=target_date,
                to_date=target_date,
                scope=scope,
                category=category,
                summary_type="daily",
            )
            if scope_cat_summary:
                summaries.append(scope_cat_summary)

        # 4. Summary by activity type
        activity_types = ["Electricity", "Air Travel", "Purchased Goods and Services"]
        for activity_type in activity_types:
            activity_summary = await self._aggregate_period(
                from_date=target_date,
                to_date=target_date,
                activity_type=activity_type,
                summary_type="daily",
            )
            if activity_summary:
                summaries.append(activity_summary)

        # 5. Summary by scope + activity type
        for scope in [2, 3]:
            for activity_type in activity_types:
                scope_activity_summary = await self._aggregate_period(
                    from_date=target_date,
                    to_date=target_date,
                    scope=scope,
                    activity_type=activity_type,
                    summary_type="daily",
                )
                if scope_activity_summary:
                    summaries.append(scope_activity_summary)

        logger.info(f"Created {len(summaries)} daily summaries for {target_date}")
        return summaries

    async def aggregate_monthly_summaries(
        self,
        year: int,
        month: int,
    ) -> list[EmissionSummaryDBModel]:
        """
        Aggregate emissions for an entire month.

        Creates same breakdown as daily but for the whole month.
        """
        # Calculate month date range
        from_date = date(year, month, 1)
        if month == 12:
            to_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            to_date = date(year, month + 1, 1) - timedelta(days=1)

        logger.info(f"Aggregating monthly emissions for {year}-{month:02d}")

        summaries = []

        # Overall summary
        overall = await self._aggregate_period(
            from_date=from_date,
            to_date=to_date,
            summary_type="monthly",
        )
        if overall:
            summaries.append(overall)

        # By scope
        for scope in [2, 3]:
            scope_summary = await self._aggregate_period(
                from_date=from_date,
                to_date=to_date,
                scope=scope,
                summary_type="monthly",
            )
            if scope_summary:
                summaries.append(scope_summary)

        # By scope + category
        for scope, category in [(3, 1), (3, 6)]:
            scope_cat_summary = await self._aggregate_period(
                from_date=from_date,
                to_date=to_date,
                scope=scope,
                category=category,
                summary_type="monthly",
            )
            if scope_cat_summary:
                summaries.append(scope_cat_summary)

        # By activity type
        activity_types = ["Electricity", "Air Travel", "Purchased Goods and Services"]
        for activity_type in activity_types:
            activity_summary = await self._aggregate_period(
                from_date=from_date,
                to_date=to_date,
                activity_type=activity_type,
                summary_type="monthly",
            )
            if activity_summary:
                summaries.append(activity_summary)

        logger.info(f"Created {len(summaries)} monthly summaries for {year}-{month:02d}")
        return summaries

    async def _aggregate_period(
        self,
        from_date: date,
        to_date: date,
        scope: Optional[int] = None,
        category: Optional[int] = None,
        activity_type: Optional[str] = None,
        summary_type: str = "daily",
    ) -> Optional[EmissionSummaryDBModel]:
        """
        Aggregate emissions for a specific period and filter combination.

        Returns:
            EmissionSummaryDBModel if data exists, None otherwise
        """
        # Build query to aggregate emission results
        stmt = (
            select(
                func.sum(EmissionResultDBModel.co2e_tonnes).label("total_co2e"),
                func.count(EmissionResultDBModel.id).label("activity_count"),
            )
            .select_from(EmissionResultDBModel)
            .join(
                EmissionFactorDBModel,
                EmissionResultDBModel.emission_factor_id == EmissionFactorDBModel.id,
            )
            .where(
                and_(
                    EmissionResultDBModel.calculation_date >= from_date,
                    EmissionResultDBModel.calculation_date <= to_date,
                )
            )
        )

        # Apply filters
        if scope is not None:
            stmt = stmt.where(EmissionFactorDBModel.scope == scope)
        if category is not None:
            stmt = stmt.where(EmissionFactorDBModel.category == category)
        if activity_type is not None:
            stmt = stmt.where(EmissionResultDBModel.activity_type == activity_type)

        result = await self.session.execute(stmt)
        row = result.one()

        # Skip if no data
        if row.total_co2e is None or row.activity_count == 0:
            return None

        # Check if summary already exists
        existing_stmt = select(EmissionSummaryDBModel).where(
            and_(
                EmissionSummaryDBModel.from_date == from_date,
                EmissionSummaryDBModel.to_date == to_date,
                EmissionSummaryDBModel.scope == scope,
                EmissionSummaryDBModel.category == category,
                EmissionSummaryDBModel.activity_type == activity_type,
                EmissionSummaryDBModel.summary_type == summary_type,
            )
        )
        existing_result = await self.session.execute(existing_stmt)
        existing_summary = existing_result.scalar_one_or_none()

        if existing_summary:
            # Update existing summary
            existing_summary.total_co2e_tonnes = row.total_co2e
            existing_summary.activity_count = row.activity_count
            logger.debug(f"Updated existing summary: {existing_summary}")
            return existing_summary
        else:
            # Create new summary
            summary = EmissionSummaryDBModel(
                from_date=from_date,
                to_date=to_date,
                scope=scope,
                category=category,
                activity_type=activity_type,
                total_co2e_tonnes=row.total_co2e,
                activity_count=row.activity_count,
                summary_type=summary_type,
            )
            self.session.add(summary)
            logger.debug(f"Created new summary: {summary}")
            return summary

    async def aggregate_custom_range(
        self,
        from_date: date,
        to_date: date,
        scope: Optional[int] = None,
        category: Optional[int] = None,
        activity_type: Optional[str] = None,
    ) -> EmissionSummaryDBModel:
        """
        Aggregate emissions for a custom date range with optional filters.

        Useful for ad-hoc reporting or specific date ranges.
        """
        logger.info(
            f"Aggregating custom range: {from_date} to {to_date}, "
            f"scope={scope}, category={category}, activity={activity_type}"
        )

        summary = await self._aggregate_period(
            from_date=from_date,
            to_date=to_date,
            scope=scope,
            category=category,
            activity_type=activity_type,
            summary_type="custom",
        )

        if not summary:
            # Return empty summary if no data
            summary = EmissionSummaryDBModel(
                from_date=from_date,
                to_date=to_date,
                scope=scope,
                category=category,
                activity_type=activity_type,
                total_co2e_tonnes=Decimal("0"),
                activity_count=0,
                summary_type="custom",
            )
            self.session.add(summary)

        await self.session.commit()
        return summary
