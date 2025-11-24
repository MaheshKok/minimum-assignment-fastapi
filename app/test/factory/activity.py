"""
Factory for Activity models following kkb_fastapi pattern.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

import factory

from app.database.schemas import (
    AirTravelActivityDBModel,
    ElectricityActivityDBModel,
    GoodsServicesActivityDBModel,
)
from app.services.calculators.unit_converter import UnitConverter
from app.test.factory.base_factory import AsyncSQLAlchemyFactory
from app.test.factory.create_async_session import async_session
from app.utils.constants import ActivityType


class ElectricityActivityFactory(AsyncSQLAlchemyFactory):
    """Factory for creating ElectricityActivity test instances."""

    class Meta:
        model = ElectricityActivityDBModel
        sqlalchemy_session = async_session
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    activity_type = ActivityType.ELECTRICITY
    date = factory.LazyFunction(date.today)
    country = factory.Sequence(lambda n: f"Test Country {n}")
    usage_kwh = Decimal("1000.0")
    source_file = None
    raw_data = {}
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class AirTravelActivityFactory(AsyncSQLAlchemyFactory):
    """Factory for creating AirTravelActivity test instances."""

    class Meta:
        model = AirTravelActivityDBModel
        sqlalchemy_session = async_session
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    activity_type = ActivityType.AIR_TRAVEL
    date = factory.LazyFunction(date.today)
    distance_miles = Decimal("500.0")
    distance_km = factory.LazyAttribute(
        lambda obj: UnitConverter.miles_to_km(obj.distance_miles)
    )
    flight_range = "Short-haul"
    passenger_class = "Economy class"
    source_file = None
    raw_data = {}
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class LongHaulBusinessTravelFactory(AirTravelActivityFactory):
    """Factory for long-haul business class flights."""

    distance_miles = Decimal("5000.0")
    distance_km = factory.LazyAttribute(
        lambda obj: UnitConverter.miles_to_km(obj.distance_miles)
    )
    flight_range = "Long-haul"
    passenger_class = "Business class"


class GoodsServicesActivityFactory(AsyncSQLAlchemyFactory):
    """Factory for creating GoodsServicesActivity test instances."""

    class Meta:
        model = GoodsServicesActivityDBModel
        sqlalchemy_session = async_session
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    activity_type = ActivityType.GOODS_SERVICES
    date = factory.LazyFunction(date.today)
    supplier_category = factory.Sequence(lambda n: f"Category {n}")
    spend_gbp = Decimal("5000.0")
    description = factory.Sequence(lambda n: f"Test purchase {n}")
    source_file = None
    raw_data = {}
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)
