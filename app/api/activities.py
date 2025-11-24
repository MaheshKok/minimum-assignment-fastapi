"""
Activity Data API router.

CRUD operations for activity data (Electricity, Air Travel, Goods & Services).
"""
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.schemas import (
    ElectricityActivityDBModel,
    AirTravelActivityDBModel,
    GoodsServicesActivityDBModel,
)
from app.pydantic_models.activity import (
    ElectricityActivityPydModel,
    ElectricityActivityCreate,
    AirTravelActivityPydModel,
    AirTravelActivityCreate,
    GoodsServicesActivityPydModel,
    GoodsServicesActivityCreate,
)
from app.services.calculators.unit_converter import UnitConverter
from app.utils.constants import ActivityType, MILES_TO_KM

router = APIRouter(
    prefix="/api/v1/activities",
    tags=["Activity Data"],
)

logger = logging.getLogger(__name__)


# Electricity Activities
@router.get("/electricity", response_model=List[ElectricityActivityPydModel])
async def list_electricity_activities(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """List electricity activities."""
    stmt = select(ElectricityActivityDBModel).where(
        ElectricityActivityDBModel.is_deleted == False
    ).offset(skip).limit(limit)
    result = await session.execute(stmt)
    activities = result.scalars().all()
    return activities


@router.post("/electricity", response_model=ElectricityActivityPydModel, status_code=status.HTTP_201_CREATED)
async def create_electricity_activity(
    activity_data: ElectricityActivityCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Create electricity activity."""
    activity_db = ElectricityActivityDBModel(
        **activity_data.model_dump(),
        activity_type=ActivityType.ELECTRICITY
    )
    session.add(activity_db)
    await session.flush()
    await session.refresh(activity_db)

    logger.info(f"Created electricity activity: {activity_db.id}")
    return activity_db


# Air Travel Activities
@router.get("/air-travel", response_model=List[AirTravelActivityPydModel])
async def list_air_travel_activities(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """List air travel activities."""
    stmt = select(AirTravelActivityDBModel).where(
        AirTravelActivityDBModel.is_deleted == False
    ).offset(skip).limit(limit)
    result = await session.execute(stmt)
    activities = result.scalars().all()
    return activities


@router.post("/air-travel", response_model=AirTravelActivityPydModel, status_code=status.HTTP_201_CREATED)
async def create_air_travel_activity(
    activity_data: AirTravelActivityCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Create air travel activity with automatic unit conversion."""
    # Calculate distance_km from miles
    distance_km = UnitConverter.miles_to_km(activity_data.distance_miles)

    activity_db = AirTravelActivityDBModel(
        date=activity_data.date,
        distance_miles=activity_data.distance_miles,
        distance_km=distance_km,
        flight_range=activity_data.flight_range,
        passenger_class=activity_data.passenger_class,
        source_file=activity_data.source_file,
        raw_data=activity_data.raw_data,
        activity_type=ActivityType.AIR_TRAVEL,
    )
    session.add(activity_db)
    await session.flush()
    await session.refresh(activity_db)

    logger.info(f"Created air travel activity: {activity_db.id}")
    return activity_db


# Goods & Services Activities
@router.get("/goods-services", response_model=List[GoodsServicesActivityPydModel])
async def list_goods_services_activities(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """List goods & services activities."""
    stmt = select(GoodsServicesActivityDBModel).where(
        GoodsServicesActivityDBModel.is_deleted == False
    ).offset(skip).limit(limit)
    result = await session.execute(stmt)
    activities = result.scalars().all()
    return activities


@router.post("/goods-services", response_model=GoodsServicesActivityPydModel, status_code=status.HTTP_201_CREATED)
async def create_goods_services_activity(
    activity_data: GoodsServicesActivityCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """Create goods & services activity."""
    activity_db = GoodsServicesActivityDBModel(
        **activity_data.model_dump(),
        activity_type=ActivityType.GOODS_SERVICES
    )
    session.add(activity_db)
    await session.flush()
    await session.refresh(activity_db)

    logger.info(f"Created goods & services activity: {activity_db.id}")
    return activity_db
