"""
Emission Aggregations API router.

Endpoints for triggering emission summary aggregations.
Pre-computes summaries for efficient querying.
"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.pydantic_models.emission_summary import (
    AggregationRequest,
    AggregationResponse,
    EmissionSummaryPydModel,
)
from app.services.aggregators import EmissionAggregator

router = APIRouter(
    prefix="/api/v1/aggregations",
    tags=["Aggregations"],
)

logger = logging.getLogger(__name__)


@router.post("/daily", response_model=AggregationResponse)
async def aggregate_daily(
    target_date: date | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Aggregate emissions for a specific day.

    Creates pre-computed summaries for all dimension combinations:
    - Overall (all scopes, categories, activities)
    - By scope (2, 3)
    - By scope + category
    - By activity type
    - By scope + activity type

    Args:
        target_date: Date to aggregate (defaults to yesterday if not provided)

    Returns:
        AggregationResponse with created summaries

    Example:
        ```
        POST /api/v1/aggregations/daily?target_date=2025-11-25
        ```
    """
    # Default to yesterday if no date provided
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    logger.info(f"Triggering daily aggregation for {target_date}")

    try:
        aggregator = EmissionAggregator(session)
        summaries = await aggregator.aggregate_daily_summaries(target_date)
        await session.commit()

        return AggregationResponse(
            success=True,
            message=f"Successfully aggregated emissions for {target_date}",
            summaries_created=len(summaries),
            summaries=[
                EmissionSummaryPydModel.model_validate(s) for s in summaries
            ],
        )
    except Exception as e:
        logger.error(f"Error during daily aggregation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to aggregate daily emissions: {str(e)}",
        )


@router.post("/monthly", response_model=AggregationResponse)
async def aggregate_monthly(
    year: int | None = None,
    month: int | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Aggregate emissions for an entire month.

    Creates pre-computed summaries for all dimension combinations for the month.
    Ideal for monthly reporting and year-over-year comparisons.

    Args:
        year: Year to aggregate (defaults to current year if not provided)
        month: Month to aggregate (1-12, defaults to last month if not provided)

    Returns:
        AggregationResponse with created summaries

    Example:
        ```
        POST /api/v1/aggregations/monthly?year=2025&month=11
        ```
    """
    # Default to last month if not provided
    if year is None or month is None:
        last_month = date.today().replace(day=1) - timedelta(days=1)
        year = year or last_month.year
        month = month or last_month.month

    # Validate month
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month must be between 1 and 12",
        )

    logger.info(f"Triggering monthly aggregation for {year}-{month:02d}")

    try:
        aggregator = EmissionAggregator(session)
        summaries = await aggregator.aggregate_monthly_summaries(year, month)
        await session.commit()

        return AggregationResponse(
            success=True,
            message=f"Successfully aggregated emissions for {year}-{month:02d}",
            summaries_created=len(summaries),
            summaries=[
                EmissionSummaryPydModel.model_validate(s) for s in summaries
            ],
        )
    except Exception as e:
        logger.error(f"Error during monthly aggregation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to aggregate monthly emissions: {str(e)}",
        )


@router.post("/custom", response_model=EmissionSummaryPydModel)
async def aggregate_custom_range(
    request: AggregationRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Aggregate emissions for a custom date range with optional filters.

    Useful for ad-hoc reporting or specific date ranges not covered by daily/monthly.
    Can filter by scope, category, and activity type.

    Request Body:
        - from_date: Start date (required for custom aggregation)
        - to_date: End date (required for custom aggregation)
        - scope: Optional scope filter (2 or 3)
        - category: Optional category filter (1 or 6)
        - activity_type: Optional activity type filter

    Returns:
        EmissionSummaryPydModel with aggregated data

    Example:
        ```json
        POST /api/v1/aggregations/custom
        {
          "aggregation_type": "custom",
          "from_date": "2025-11-01",
          "to_date": "2025-11-30",
          "scope": 2,
          "activity_type": "Electricity"
        }
        ```
    """
    if not request.from_date or not request.to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date and to_date are required for custom aggregation",
        )

    if request.from_date > request.to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be before or equal to to_date",
        )

    logger.info(
        f"Triggering custom aggregation: {request.from_date} to {request.to_date}"
    )

    try:
        aggregator = EmissionAggregator(session)
        summary = await aggregator.aggregate_custom_range(
            from_date=request.from_date,
            to_date=request.to_date,
            scope=request.scope if hasattr(request, 'scope') else None,
            category=request.category if hasattr(request, 'category') else None,
            activity_type=request.activity_type if hasattr(request, 'activity_type') else None,
        )

        return EmissionSummaryPydModel.model_validate(summary)
    except Exception as e:
        logger.error(f"Error during custom aggregation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to aggregate custom range: {str(e)}",
        )


@router.post("/backfill", response_model=AggregationResponse)
async def backfill_summaries(
    from_date: date,
    to_date: date,
    aggregation_type: str = "daily",
    session: AsyncSession = Depends(get_db_session),
):
    """
    Backfill aggregations for a historical date range.

    Useful for populating summaries for existing historical data.
    Runs daily or monthly aggregations for each period in the range.

    Args:
        from_date: Start date for backfill
        to_date: End date for backfill
        aggregation_type: Type of aggregation (daily or monthly)

    Returns:
        AggregationResponse with total summaries created

    Example:
        ```
        POST /api/v1/aggregations/backfill?from_date=2025-01-01&to_date=2025-11-30&aggregation_type=monthly
        ```
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be before or equal to to_date",
        )

    logger.info(
        f"Triggering backfill: {from_date} to {to_date}, type={aggregation_type}"
    )

    try:
        aggregator = EmissionAggregator(session)
        all_summaries = []

        if aggregation_type == "daily":
            # Backfill daily summaries
            current_date = from_date
            while current_date <= to_date:
                summaries = await aggregator.aggregate_daily_summaries(current_date)
                all_summaries.extend(summaries)
                current_date += timedelta(days=1)

        elif aggregation_type == "monthly":
            # Backfill monthly summaries
            current_date = from_date.replace(day=1)
            end_date = to_date.replace(day=1)

            while current_date <= end_date:
                summaries = await aggregator.aggregate_monthly_summaries(
                    current_date.year, current_date.month
                )
                all_summaries.extend(summaries)

                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="aggregation_type must be 'daily' or 'monthly'",
            )

        await session.commit()

        return AggregationResponse(
            success=True,
            message=f"Successfully backfilled {aggregation_type} summaries from {from_date} to {to_date}",
            summaries_created=len(all_summaries),
            summaries=[
                EmissionSummaryPydModel.model_validate(s) for s in all_summaries[:100]  # Limit response size
            ],
        )
    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to backfill summaries: {str(e)}",
        )
