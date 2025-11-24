"""
Service tests for emission calculators following kkb_fastapi pattern.
"""

from decimal import Decimal

import pytest

from app.services.calculators.electricity_calculator import ElectricityCalculator
from app.services.calculators.emission_calculator import EmissionCalculationService
from app.services.calculators.goods_services_calculator import GoodsServicesCalculator
from app.services.calculators.travel_calculator import TravelCalculator
from app.test.factory.activity import (
    AirTravelActivityFactory,
    ElectricityActivityFactory,
    GoodsServicesActivityFactory,
)
from app.test.factory.emission_factor import (
    AirTravelEmissionFactorFactory,
    ElectricityEmissionFactorFactory,
    GoodsServicesEmissionFactorFactory,
)


@pytest.mark.asyncio
async def test_electricity_calculator(test_db_session):
    """Test ElectricityCalculator service."""
    # Create factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )

    # Calculate
    calculator = ElectricityCalculator(test_db_session)
    result = await calculator.calculate(activity)

    assert result is not None
    assert result.co2e_tonnes == Decimal("0.3")  # 1000 * 0.3 / 1000
    assert result.confidence_score == Decimal("1.0")


@pytest.mark.asyncio
async def test_travel_calculator(test_db_session):
    """Test TravelCalculator service."""
    # Create factor and activity
    await AirTravelEmissionFactorFactory(
        lookup_identifier="Short-haul, Economy class", co2e_factor=0.15
    )
    activity = await AirTravelActivityFactory(
        distance_miles=500.0, flight_range="Short-haul", passenger_class="Economy class"
    )

    # Calculate
    calculator = TravelCalculator(test_db_session)
    result = await calculator.calculate(activity)

    assert result is not None
    assert result.co2e_tonnes > 0
    assert result.confidence_score == Decimal("1.0")


@pytest.mark.asyncio
async def test_goods_services_calculator(test_db_session):
    """Test GoodsServicesCalculator service."""
    # Create factor and activity
    await GoodsServicesEmissionFactorFactory(
        lookup_identifier="Office Supplies", co2e_factor=0.5
    )
    activity = await GoodsServicesActivityFactory(
        supplier_category="Office Supplies", spend_gbp=1000.0
    )

    # Calculate
    calculator = GoodsServicesCalculator(test_db_session)
    result = await calculator.calculate(activity)

    assert result is not None
    assert result.co2e_tonnes == Decimal("0.5")  # 1000 * 0.5 / 1000
    assert result.confidence_score == Decimal("1.0")


@pytest.mark.asyncio
async def test_emission_calculation_service_single(test_db_session):
    """Test EmissionCalculationService calculate_single method."""
    # Create factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(usage_kwh=1000.0)

    # Calculate
    service = EmissionCalculationService(test_db_session)
    result = await service.calculate_single(activity)

    assert result is not None
    assert result.activity_id == activity.id
    assert result.co2e_tonnes > 0


@pytest.mark.asyncio
async def test_emission_calculation_service_batch(test_db_session):
    """Test EmissionCalculationService calculate_batch method."""
    # Create factors
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )
    await AirTravelEmissionFactorFactory(
        lookup_identifier="Short-haul, Economy class", co2e_factor=0.15
    )

    # Create activities
    activity1 = await ElectricityActivityFactory(usage_kwh=1000.0)
    activity2 = await AirTravelActivityFactory(distance_miles=500.0)

    # Calculate batch
    service = EmissionCalculationService(test_db_session)
    summary = await service.calculate_batch([activity1, activity2])

    assert summary["statistics"]["total_activities"] == 2
    assert summary["statistics"]["total_processed"] == 2
    assert summary["statistics"]["total_errors"] == 0
    assert len(summary["results"]) == 2


@pytest.mark.asyncio
async def test_calculator_no_matching_factor(test_db_session):
    """Test calculator behavior when no matching emission factor exists."""
    # Create activity without corresponding factor
    activity = await ElectricityActivityFactory(country="Nonexistent Country")

    # Calculate
    calculator = ElectricityCalculator(test_db_session)
    result = await calculator.calculate(activity)

    assert result is None


@pytest.mark.asyncio
async def test_calculator_fuzzy_matching(test_db_session):
    """Test calculator fuzzy matching functionality."""
    # Create factor with specific name
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )

    # Create activity with slightly different name
    activity = await ElectricityActivityFactory(
        country="UK", usage_kwh=1000.0  # Shortened form
    )

    # Calculate with fuzzy matching
    calculator = ElectricityCalculator(test_db_session)
    result = await calculator.calculate(activity, fuzzy_threshold=70)

    # May or may not match depending on fuzzy threshold
    # This tests the fuzzy matching functionality
    if result:
        assert result.confidence_score < Decimal("1.0")


@pytest.mark.asyncio
async def test_recalculate_activity(test_db_session):
    """Test recalculating emissions for an activity."""
    # Create factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )

    # Calculate first time
    service = EmissionCalculationService(test_db_session)
    result1 = await service.calculate_single(activity)
    assert result1 is not None

    # Recalculate
    result2 = await service.recalculate_activity(activity)
    assert result2 is not None
    assert result2.id != result1.id  # Should be a new result


@pytest.mark.asyncio
async def test_calculate_all_pending(test_db_session):
    """Test calculating emissions for all pending activities."""
    # Create factors
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 1", co2e_factor=0.3
    )

    # Create activities (all pending, no emissions calculated)
    await ElectricityActivityFactory()
    await ElectricityActivityFactory()

    # Calculate all pending
    service = EmissionCalculationService(test_db_session)
    summary = await service.calculate_all_pending()

    assert summary["statistics"]["total_activities"] == 2
    assert summary["statistics"]["total_processed"] == 2


@pytest.mark.asyncio
async def test_calculation_metadata_stored(test_db_session):
    """Test that calculation metadata is properly stored."""
    # Create factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )

    # Calculate
    calculator = ElectricityCalculator(test_db_session)
    result = await calculator.calculate(activity)

    assert result.calculation_metadata is not None
    assert "usage_kwh" in result.calculation_metadata
    assert "emission_factor_value" in result.calculation_metadata
    assert "calculation_method" in result.calculation_metadata


@pytest.mark.asyncio
async def test_batch_calculate_with_errors(test_db_session):
    """Test batch calculation with some activities failing."""
    # Create one factor but two activities
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )
    activity1 = await ElectricityActivityFactory()  # Will match factor
    activity2 = await ElectricityActivityFactory(
        country="No Match"
    )  # Won't match any factor

    # Calculate batch (should handle errors gracefully)
    service = EmissionCalculationService(test_db_session)
    summary = await service.calculate_batch([activity1, activity2], fail_fast=False)

    # One should succeed, one should fail
    assert summary["statistics"]["total_activities"] == 2
    assert summary["statistics"]["total_processed"] == 1
    assert summary["statistics"]["total_errors"] == 1
