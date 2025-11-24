"""
Emissions Reports API router.

Generate comprehensive emission reports.
"""

import logging
from datetime import date as today_date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.schemas import EmissionFactorDBModel, EmissionResultDBModel
from app.pydantic_models.calculation import EmissionReportResponse, EmissionSummary
from app.utils.constants import Scope

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"],
)

logger = logging.getLogger(__name__)


@router.get("/emissions", response_model=EmissionReportResponse)
async def generate_emissions_report(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Generate comprehensive emissions report.

    Includes:
    - Total emissions by scope and category
    - Breakdown by activity type
    - Individual calculation results

    Returns:
        EmissionReportResponse with summary and detailed breakdown

    Example:
        ```
        GET /api/v1/reports/emissions
        ```
    """

    logger.info("Generating emissions report")

    # Query all emission results with their factors
    stmt = select(EmissionResultDBModel, EmissionFactorDBModel).join(
        EmissionFactorDBModel,
        EmissionResultDBModel.emission_factor_id == EmissionFactorDBModel.id,
    )
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

    # Create summary
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
