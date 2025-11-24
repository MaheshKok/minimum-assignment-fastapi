"""
Emissions Calculations API router.

Calculate emissions for activities.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.pydantic_models.calculation import (
    EmissionCalculationRequest,
    EmissionResultPydModel,
)

router = APIRouter(
    prefix="/api/v1/calculations",
    tags=["Calculations"],
)

logger = logging.getLogger(__name__)


@router.post("/calculate", response_model=list[EmissionResultPydModel])
async def calculate_emissions(
    request: EmissionCalculationRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Calculate emissions for given activity IDs.

    This endpoint will:
    1. Fetch activities by IDs
    2. Match with appropriate emission factors
    3. Calculate CO2e emissions
    4. Store and return results

    Args:
        request: EmissionCalculationRequest with activity_ids and recalculate flag
        session: Database session

    Returns:
        List of EmissionResultPydModel instances

    Example:
        ```
        POST /api/v1/calculations/calculate
        {
            "activity_ids": ["uuid1", "uuid2"],
            "recalculate": false
        }
        ```
    """
    from sqlalchemy import select

    from app.database.schemas import (
        AirTravelActivityDBModel,
        ElectricityActivityDBModel,
        GoodsServicesActivityDBModel,
    )
    from app.services.calculators.emission_calculator import EmissionCalculationService

    logger.info(f"Calculating emissions for {len(request.activity_ids)} activities")

    service = EmissionCalculationService(session)
    results = []

    # Process each activity ID
    for activity_id in request.activity_ids:
        # Try to find activity in each table
        activity = None

        # Check electricity activities
        stmt = select(ElectricityActivityDBModel).where(
            ElectricityActivityDBModel.id == activity_id
        )
        result = await session.execute(stmt)
        activity = result.scalars().first()

        # Check air travel activities if not found
        if not activity:
            stmt = select(AirTravelActivityDBModel).where(
                AirTravelActivityDBModel.id == activity_id
            )
            result = await session.execute(stmt)
            activity = result.scalars().first()

        # Check goods/services activities if not found
        if not activity:
            stmt = select(GoodsServicesActivityDBModel).where(
                GoodsServicesActivityDBModel.id == activity_id
            )
            result = await session.execute(stmt)
            activity = result.scalars().first()

        if not activity:
            logger.warning(f"Activity not found: {activity_id}")
            continue

        try:
            # Calculate or recalculate
            if request.recalculate:
                emission_result = await service.recalculate_activity(activity)
            else:
                emission_result = await service.calculate_single(activity)

            if emission_result:
                results.append(emission_result)
        except Exception as e:
            logger.error(
                f"Failed to calculate emissions for activity {activity_id}: {e}"
            )
            continue

    await session.commit()

    logger.info(f"Successfully calculated emissions for {len(results)} activities")

    return results
