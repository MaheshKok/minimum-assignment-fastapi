"""
Factory for EmissionFactor models following kkb_fastapi pattern.
"""
import uuid
from datetime import datetime
from decimal import Decimal

import factory

from app.database.schemas import EmissionFactorDBModel
from app.test.factory.base_factory import AsyncSQLAlchemyFactory
from app.test.factory.create_async_session import async_session
from app.utils.constants import ActivityType, Scope


class EmissionFactorFactory(AsyncSQLAlchemyFactory):
    """Factory for creating EmissionFactor test instances."""

    class Meta:
        model = EmissionFactorDBModel
        sqlalchemy_session = async_session
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    activity_type = ActivityType.ELECTRICITY
    lookup_identifier = factory.Sequence(lambda n: f"Country {n}")
    unit = "kWh"
    co2e_factor = Decimal("0.5")
    scope = Scope.SCOPE_2
    category = None
    source = "Test Data"
    notes = factory.Sequence(lambda n: f"Test emission factor {n}")
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class ElectricityEmissionFactorFactory(EmissionFactorFactory):
    """Factory for electricity-specific emission factors."""

    activity_type = ActivityType.ELECTRICITY
    lookup_identifier = factory.Sequence(lambda n: f"Test Country {n}")
    unit = "kWh"
    scope = Scope.SCOPE_2
    category = None
    co2e_factor = Decimal("0.3")


class AirTravelEmissionFactorFactory(EmissionFactorFactory):
    """Factory for air travel-specific emission factors."""

    activity_type = ActivityType.AIR_TRAVEL
    lookup_identifier = factory.Sequence(
        lambda n: f"Short-haul, {'Economy' if n % 2 == 0 else 'Business'} class"
    )
    unit = "passenger.km"
    scope = Scope.SCOPE_3
    category = 6
    co2e_factor = Decimal("0.15")


class GoodsServicesEmissionFactorFactory(EmissionFactorFactory):
    """Factory for goods/services-specific emission factors."""

    activity_type = ActivityType.GOODS_SERVICES
    lookup_identifier = factory.Sequence(lambda n: f"Category {n}")
    unit = "GBP"
    scope = Scope.SCOPE_3
    category = 1
    co2e_factor = Decimal("0.8")
