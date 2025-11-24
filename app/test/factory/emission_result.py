"""
Factory for EmissionResult models following kkb_fastapi pattern.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

import factory

from app.database.schemas import EmissionResultDBModel
from app.test.factory.base_factory import AsyncSQLAlchemyFactory
from app.test.factory.create_async_session import async_session
from app.test.factory.emission_factor import EmissionFactorFactory
from app.test.factory.activity import ElectricityActivityFactory
from app.utils.constants import ActivityType


class EmissionResultFactory(AsyncSQLAlchemyFactory):
    """Factory for creating EmissionResult test instances."""

    class Meta:
        model = EmissionResultDBModel
        sqlalchemy_session = async_session
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    activity_type = ActivityType.ELECTRICITY
    activity_id = factory.LazyFunction(uuid.uuid4)
    emission_factor_id = factory.SubFactory(EmissionFactorFactory)
    co2e_tonnes = Decimal("0.5")
    confidence_score = Decimal("1.0")
    calculation_metadata = {
        "usage_kwh": "1000",
        "country": "Test Country",
        "emission_factor_value": "0.5",
        "unit": "kWh",
        "calculation_method": "exact",
    }
    calculation_date = factory.LazyFunction(date.today)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class ElectricityEmissionResultFactory(EmissionResultFactory):
    """Factory for electricity emission results."""

    activity_type = ActivityType.ELECTRICITY
    emission_factor_id = factory.SubFactory(EmissionFactorFactory)
    co2e_tonnes = Decimal("0.3")
    calculation_metadata = {
        "usage_kwh": "1000",
        "country": "United Kingdom",
        "matched_country": "United Kingdom",
        "emission_factor_value": "0.3",
        "unit": "kWh",
        "calculation_method": "exact",
    }
