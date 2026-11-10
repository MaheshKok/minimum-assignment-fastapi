"""
Activity Data API router.

List and create operations for activity data (Electricity, Air Travel, Goods & Services).
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.repositories import (
    AirTravelActivityRepository,
    ElectricityActivityRepository,
    GoodsServicesActivityRepository,
)
from app.pydantic_models.activity import (
    AirTravelActivityCreate,
    AirTravelActivityPydModel,
    ElectricityActivityCreate,
    ElectricityActivityPydModel,
    GoodsServicesActivityCreate,
    GoodsServicesActivityPydModel,
)
from app.services.calculators.unit_converter import UnitConverter
from app.utils.constants import ActivityType

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


@router.post(
    "/electricity",
    response_model=ElectricityActivityPydModel,
    status_code=status.HTTP_201_CREATED,
)
async def create_electricity_activity(
    activity: ElectricityActivityCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Create an electricity activity."""
    repo = ElectricityActivityRepository(session)
    created = await repo.create(activity_type=ActivityType.ELECTRICITY, **activity.model_dump())
    logger.info(f"Created electricity activity {created.id}")
    return created


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


@router.post(
    "/air-travel",
    response_model=AirTravelActivityPydModel,
    status_code=status.HTTP_201_CREATED,
)
async def create_air_travel_activity(
    activity: AirTravelActivityCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Create an air travel activity; distance_km is derived from distance_miles."""
    repo = AirTravelActivityRepository(session)
    created = await repo.create(
        activity_type=ActivityType.AIR_TRAVEL,
        distance_km=UnitConverter.miles_to_km(activity.distance_miles),
        **activity.model_dump(),
    )
    logger.info(f"Created air travel activity {created.id}")
    return created


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


@router.post(
    "/goods-services",
    response_model=GoodsServicesActivityPydModel,
    status_code=status.HTTP_201_CREATED,
)
async def create_goods_services_activity(
    activity: GoodsServicesActivityCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a goods & services activity."""
    repo = GoodsServicesActivityRepository(session)
    created = await repo.create(activity_type=ActivityType.GOODS_SERVICES, **activity.model_dump())
    logger.info(f"Created goods & services activity {created.id}")
    return created
