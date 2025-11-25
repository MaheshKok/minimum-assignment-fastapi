"""
Activity Data API router.

Read-only operations for activity data (Electricity, Air Travel, Goods & Services).
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.repositories import (
    AirTravelActivityRepository,
    ElectricityActivityRepository,
    GoodsServicesActivityRepository,
)
from app.pydantic_models.activity import (
    AirTravelActivityPydModel,
    ElectricityActivityPydModel,
    GoodsServicesActivityPydModel,
)

router = APIRouter(
    prefix="/api/v1/activities",
    tags=["Activity Data"],
)

logger = logging.getLogger(__name__)


# Electricity Activities
@router.get("/electricity", response_model=list[ElectricityActivityPydModel])
async def list_electricity_activities(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """List electricity activities."""
    repo = ElectricityActivityRepository(session)
    activities = await repo.get_all_active(skip=skip, limit=limit)
    return activities


@router.get("/electricity/{activity_id}", response_model=ElectricityActivityPydModel)
async def get_electricity_activity(
    activity_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get electricity activity by ID."""
    repo = ElectricityActivityRepository(session)
    activity = await repo.get_by_id_active(UUID(activity_id))

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Electricity activity {activity_id} not found",
        )

    return activity




# Air Travel Activities
@router.get("/air-travel", response_model=list[AirTravelActivityPydModel])
async def list_air_travel_activities(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """List air travel activities."""
    repo = AirTravelActivityRepository(session)
    activities = await repo.get_all_active(skip=skip, limit=limit)
    return activities




# Goods & Services Activities
@router.get("/goods-services", response_model=list[GoodsServicesActivityPydModel])
async def list_goods_services_activities(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """List goods & services activities."""
    repo = GoodsServicesActivityRepository(session)
    activities = await repo.get_all_active(skip=skip, limit=limit)
    return activities
