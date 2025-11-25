"""
Emissions Reports API router.

Generate comprehensive emission reports.
"""

import logging
from datetime import date as today_date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.schemas import EmissionFactorDBModel, EmissionResultDBModel
from app.pydantic_models.calculation import EmissionReportResponse, EmissionSummary
from app.utils.constants import (
    ActivityTypeEnum,
    CategoryEnum,
    Scope,
    ScopeEnum,
    SortOrderEnum,
)

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"],
)

logger = logging.getLogger(__name__)


@router.get("/emissions", response_model=EmissionReportResponse)
async def generate_emissions_report(
    scope: ScopeEnum | None = Query(
        None, description="Filter by GHG Protocol scope (2 or 3)", example=2
    ),
    category: CategoryEnum | None = Query(
        None,
        description="Filter by Scope 3 category (1=Purchased Goods, 6=Business Travel)",
        example=1,
    ),
    activity: ActivityTypeEnum | None = Query(
        None, description="Filter by activity type", example="Electricity"
    ),
    sort_by_co2e: SortOrderEnum | None = Query(
        None, description="Sort by CO2e emissions (asc or desc)", example="desc"
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Generate comprehensive emissions report with filtering and sorting.

    Query Parameters:
    - scope: Filter by GHG Protocol scope (2 or 3)
    - category: Filter by Scope 3 category (1 or 6)
    - activity: Filter by activity type
    - sort_by_co2e: Sort by CO2e emissions ('asc' or 'desc')

    Includes:
    - Total emissions by scope and category
    - Breakdown by activity type
    - Individual calculation results

    Returns:
        EmissionReportResponse with summary and detailed breakdown

    Example:
        ```
        GET /api/v1/reports/emissions?scope=2&sort_by_co2e=desc
        GET /api/v1/reports/emissions?scope=3&category=1
        GET /api/v1/reports/emissions?activity=Electricity
        ```
    """

    logger.info(
        f"Generating emissions report with filters: scope={scope}, category={category}, activity={activity}, sort={sort_by_co2e}"
    )

    # Build query with filters
    stmt = select(EmissionResultDBModel, EmissionFactorDBModel).join(
        EmissionFactorDBModel,
        EmissionResultDBModel.emission_factor_id == EmissionFactorDBModel.id,
    )

    # Apply filters
    filters = []
    if scope is not None:
        filters.append(EmissionFactorDBModel.scope == scope.value)
    if category is not None:
        filters.append(EmissionFactorDBModel.category == category.value)
    if activity is not None:
        filters.append(EmissionResultDBModel.activity_type == activity.value)

    if filters:
        stmt = stmt.where(and_(*filters))

    # Apply sorting
    if sort_by_co2e == SortOrderEnum.DESC:
        stmt = stmt.order_by(desc(EmissionResultDBModel.co2e_tonnes))
    elif sort_by_co2e == SortOrderEnum.ASC:
        stmt = stmt.order_by(EmissionResultDBModel.co2e_tonnes)

    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        # Return empty report if no data
        empty_summary = EmissionSummary(
            total_co2e_tonnes=Decimal("0"),
            scope_2_tonnes=Decimal("0"),
            scope_3_tonnes=Decimal("0"),
            scope_3_category_1_tonnes=Decimal("0"),
            scope_3_category_6_tonnes=Decimal("0"),
            total_activities=0,
            calculation_date=today_date.today(),
        )
        return EmissionReportResponse(
            summary=empty_summary,
            results=[],
            breakdown_by_activity_type={},
        )

    # Extract results and factors
    emission_results = []
    total_co2e = Decimal("0")
    scope_2_total = Decimal("0")
    scope_3_total = Decimal("0")
    scope_3_category_1 = Decimal("0")
    scope_3_category_6 = Decimal("0")
    breakdown_by_type = {}

    for emission_result, emission_factor in rows:
        emission_results.append(emission_result)
        co2e = emission_result.co2e_tonnes
        total_co2e += co2e

        # Aggregate by scope
        if emission_factor.scope == Scope.SCOPE_2:
            scope_2_total += co2e
        elif emission_factor.scope == Scope.SCOPE_3:
            scope_3_total += co2e

            # Aggregate by Scope 3 category
            if emission_factor.category == 1:
                scope_3_category_1 += co2e
            elif emission_factor.category == 6:
                scope_3_category_6 += co2e

        # Aggregate by activity type (convert to snake_case for consistency)
        activity_type = emission_result.activity_type
        # Convert "Electricity" -> "electricity", "Purchased Goods and Services" -> "goods_services"
        activity_type_key = (
            activity_type.lower()
            .replace(" ", "_")
            .replace("purchased_", "")
            .replace("and_", "")
        )
        if activity_type_key not in breakdown_by_type:
            breakdown_by_type[activity_type_key] = Decimal("0")
        breakdown_by_type[activity_type_key] += co2e

    # Create summary (convert Decimal to float for clean JSON serialization)
    summary = EmissionSummary(
        total_co2e_tonnes=total_co2e,
        scope_2_tonnes=scope_2_total,
        scope_3_tonnes=scope_3_total,
        scope_3_category_1_tonnes=scope_3_category_1,
        scope_3_category_6_tonnes=scope_3_category_6,
        total_activities=len(emission_results),
        calculation_date=today_date.today(),
    )

    logger.info(
        f"Report generated: {len(emission_results)} activities, "
        f"{total_co2e} tonnes CO2e total"
    )

    return EmissionReportResponse(
        summary=summary,
        results=emission_results,
        breakdown_by_activity_type=breakdown_by_type,
    )


@router.get("/emissions/totals", response_model=EmissionSummary)
async def get_emission_totals(
    scope: ScopeEnum | None = Query(
        None, description="Filter by GHG Protocol scope (2 or 3)", example=2
    ),
    category: CategoryEnum | None = Query(
        None,
        description="Filter by Scope 3 category (1=Purchased Goods, 6=Business Travel)",
        example=1,
    ),
    activity: ActivityTypeEnum | None = Query(
        None, description="Filter by activity type", example="Electricity"
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Calculate emission totals with optional filtering.

    Query Parameters:
    - scope: Filter by GHG Protocol scope (2 or 3)
    - category: Filter by Scope 3 category (1 or 6)
    - activity: Filter by activity type

    Returns:
        EmissionSummary with total CO2e emissions broken down by scope and category

    Example:
        ```
        GET /api/v1/reports/emissions/totals
        GET /api/v1/reports/emissions/totals?scope=2
        GET /api/v1/reports/emissions/totals?scope=3&category=1
        ```
    """

    logger.info(
        f"Calculating emission totals with filters: scope={scope}, category={category}, activity={activity}"
    )

    # Build query with filters
    stmt = select(EmissionResultDBModel, EmissionFactorDBModel).join(
        EmissionFactorDBModel,
        EmissionResultDBModel.emission_factor_id == EmissionFactorDBModel.id,
    )

    # Apply filters
    filters = []
    if scope is not None:
        filters.append(EmissionFactorDBModel.scope == scope.value)
    if category is not None:
        filters.append(EmissionFactorDBModel.category == category.value)
    if activity is not None:
        filters.append(EmissionResultDBModel.activity_type == activity.value)

    if filters:
        stmt = stmt.where(and_(*filters))

    result = await session.execute(stmt)
    rows = result.all()

    # Calculate totals
    total_co2e = Decimal("0")
    scope_2_total = Decimal("0")
    scope_3_total = Decimal("0")
    scope_3_category_1 = Decimal("0")
    scope_3_category_6 = Decimal("0")
    total_activities = 0

    for emission_result, emission_factor in rows:
        co2e = emission_result.co2e_tonnes
        total_co2e += co2e
        total_activities += 1

        # Aggregate by scope
        if emission_factor.scope == Scope.SCOPE_2:
            scope_2_total += co2e
        elif emission_factor.scope == Scope.SCOPE_3:
            scope_3_total += co2e

            # Aggregate by Scope 3 category
            if emission_factor.category == 1:
                scope_3_category_1 += co2e
            elif emission_factor.category == 6:
                scope_3_category_6 += co2e

    summary = EmissionSummary(
        total_co2e_tonnes=total_co2e,
        scope_2_tonnes=scope_2_total,
        scope_3_tonnes=scope_3_total,
        scope_3_category_1_tonnes=scope_3_category_1,
        scope_3_category_6_tonnes=scope_3_category_6,
        total_activities=total_activities,
        calculation_date=today_date.today(),
    )

    logger.info(
        f"Emission totals calculated: {total_co2e} tonnes CO2e from {total_activities} activities"
    )

    return summary
